import ast
from contextlib import nullcontext
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from enrichment.skills import extract_skills
from sources.contracts import digest, validate_config
from sources.runtime import collect_source, ConfiguredParser, run_configured_sources
from storage.paths import staging_file
from transformation.quality import validate_record
from transformation.salary import split_salary_range
from test_source_engine import config, FakeFetcher


class SourcePipelineTests(unittest.TestCase):
    def accepted(self):
        spec = config()
        return {"config": spec, "config_hash": digest(spec), "enabled": True,
                "approval": {"actor": "reviewer", "terms_reviewed": True}}

    def test_dynamic_jobs_use_existing_quality_and_skills_contracts(self):
        storage = Mock()
        storage.contains.return_value = False
        storage.save.return_value = True
        collect_source(self.accepted(), FakeFetcher(), storage)
        raw_data = storage.save.call_args_list[0].args[0]
        raw = SimpleNamespace(source="example_jobs", id=uuid4(), raw=raw_data["raw"])
        staging = ConfiguredParser().parse_raw(raw)
        normalized, issues = validate_record(staging | {"source": raw.source, "external_reference_id": raw_data["external_reference_id"]}, split_salary_range)
        self.assertEqual(issues, [])
        self.assertEqual(extract_skills(normalized["job_description"])["skills_required"], ["Python", "SQL"])
        self.assertIn("example_jobs", staging_file("example_jobs", "run").parts)

    def test_collection_rejects_unapproved_or_modified_configuration(self):
        for change in ({"enabled": False}, {"config_hash": "modified"}, {"approval": {}}):
            with self.assertRaises(ValueError):
                collect_source(self.accepted() | change, FakeFetcher(), Mock())

    def test_generic_runner_uses_the_same_source_and_run_for_parser_and_loader(self):
        modules = {}
        for name in ("db.engine", "db.models", "staging.parsers", "storage.postgres", "transformation.loaders"):
            modules[name] = ModuleType(name)
        db = Mock()
        modules["db.engine"].db_context = lambda: nullcontext(db)
        modules["db.models"].Raw = object()
        parser = Mock()
        modules["staging.parsers"].JobsParser = parser
        storage = Mock()
        storage.contains.return_value = False
        storage.save.return_value = True
        modules["storage.postgres"].PostgreSQLRawStorage = Mock(return_value=storage)
        loader = Mock()
        modules["transformation.loaders"].loader = loader
        registry = Mock()
        registry.active.return_value = [self.accepted()]
        with patch.dict(sys.modules, modules):
            reports = run_configured_sources("run-123", registry, fetcher_factory=lambda spec: FakeFetcher())
        self.assertEqual(reports[0]["source"], "example_jobs")
        parser.return_value.parse.assert_called_once_with("run-123")
        self.assertEqual(parser.call_args.args[2], "example_jobs")
        loader.assert_called_once_with(db, staging_file("example_jobs", "run-123"), source="example_jobs", run_id="run-123")

    def test_example_configuration_passes_runtime_validation(self):
        path = Path(__file__).resolve().parents[1] / "examples/sources/example_jobs.json"
        validate_config(json.loads(path.read_text()))

    def test_common_salary_parser_retains_existing_behavior(self):
        self.assertEqual(split_salary_range("NZ$80K - $100K per annum"), (80000.0, 100000.0, "year"))
        self.assertEqual(split_salary_range("$35 per hour"), (35.0, 35.0, "hour"))

    def test_orchestrator_runs_configured_sources_before_transform(self):
        import asyncio
        path = Path(__file__).resolve().parents[1] / "src/orchestrator.py"
        tree = ast.parse(path.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "main")
        calls = []

        async def to_thread(function, *args):
            return function(*args)

        namespace = {"asyncio": SimpleNamespace(gather=asyncio.gather, to_thread=to_thread),
                     "uuid4": lambda: "run", "db_context": lambda: nullcontext(Mock()), "logger": Mock()}
        for name in ("jobs_govt_collector", "trade_me_collector", "jobs_govt_parser", "trade_me_parser", "jobs_govt_loader", "trade_me_loader"):
            namespace["run_" + name] = Mock()
        namespace["run_configured_sources"] = lambda run_id: calls.append(("configured", run_id))
        namespace["run_transform"] = lambda: calls.append(("transform",))
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
        asyncio.run(namespace["main"]())
        self.assertEqual(calls, [("configured", "run"), ("transform",)])
