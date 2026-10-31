import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from uuid import uuid4

from enrichment.descriptions import trademe_description
from enrichment.skills import extract_skills


class DescriptionPipelineTests(unittest.TestCase):
    def test_trademe_description_reaches_staging(self):
        path = Path(__file__).resolve().parents[1] / "src/staging/parsers.py"
        tree = ast.parse(path.read_text())
        node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TradeMeParser")
        namespace = {"Parser": object, "Raw": object, "json": json, "trademe_description": trademe_description,
                     "dotnet_date_to_string": lambda value: None}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        raw = SimpleNamespace(id=uuid4(), job_title="Engineer", job_url="/job", raw=json.dumps({
            "Body": "<h2>Essential skills</h2><p>Python and SQL</p>", "Company": "Example",
        }))
        result = namespace["TradeMeParser"]().parse_raw(raw)
        self.assertEqual(result["job_description"], "Essential skills\nPython and SQL")
        self.assertEqual(result["description_kind"], "full")
        self.assertEqual(extract_skills(result["job_description"])["skills_required"], ["Python", "SQL"])

    def test_transformation_retains_description_and_skill_columns(self):
        path = Path(__file__).resolve().parents[1] / "src/transformation/transform.py"
        tree = ast.parse(path.read_text())
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "transform_data")
        model = Mock()
        namespace = {"StagingRaw": dict, "split_salary_range": lambda value: (None, None, None),
                     "normalize_position_type": lambda value: (None, None), "JobPosting": model,
                     "extract_skills": extract_skills, "clean_string": lambda value: value}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        fields = {name: None for name in ("source", "external_reference_id", "job_title", "employer", "location", "category", "date_listed", "closing_date", "attachment", "file_links", "website", "job_url")}
        fields.update(job_description="Python is required. SQL is preferred.", description_kind="full")
        namespace["transform_data"](fields)
        self.assertEqual(model.call_args.kwargs["skills_required"], ["Python"])
        self.assertEqual(model.call_args.kwargs["skills_mentioned"], ["Python", "SQL"])
        self.assertEqual(model.call_args.kwargs["job_description"], fields["job_description"])

    def test_schema_upgrade_runs_all_additive_statements_in_one_transaction(self):
        path = Path(__file__).resolve().parents[1] / "src/db/migrations.py"
        tree = ast.parse(path.read_text())
        nodes = [node for node in tree.body if isinstance(node, (ast.Assign, ast.FunctionDef))]
        engine = Mock()
        connection = Mock()
        from contextlib import nullcontext
        engine.begin.return_value = nullcontext(connection)
        namespace = {"engine": engine, "text": lambda value: value}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
        namespace["upgrade_job_descriptions"]()
        self.assertEqual(connection.execute.call_count, 8)
        for call in connection.execute.call_args_list:
            self.assertIn("ADD COLUMN IF NOT EXISTS", call.args[0])
