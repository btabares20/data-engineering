import ast
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock

from storage.local import LocalStorage
from storage.paths import verify_manifest, write_manifest


class LoaderTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "jobs.jsonl"
        LocalStorage().save(self.path, [{"raw_id": "raw-id", "job_title": "Engineer", "unknown_source_field": "ignored"}])
        write_manifest(self.path, "trade_me", "run", 1)
        path = Path(__file__).resolve().parents[1] / "src/transformation/loaders.py"
        tree = ast.parse(path.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
        self.statement = Mock()
        self.statement.values.return_value = self.statement
        self.statement.excluded = {"job_title": "excluded title"}
        self.statement.on_conflict_do_update.return_value = self.statement
        model = SimpleNamespace(__table__=SimpleNamespace(columns=[SimpleNamespace(name=name) for name in ("raw_id", "job_title")]))
        namespace = {
            "Session": object, "verify_manifest": verify_manifest, "json": json,
            "logger": Mock(), "Raw": SimpleNamespace(id=None, source=None), "Staging": model,
            "insert": Mock(return_value=self.statement), "func": Mock(),
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
        self.loader = namespace["loader"]
        self.db = Mock()

    def test_wrong_run_is_rejected_before_database_work(self):
        with self.assertRaises(ValueError):
            self.loader(self.db, self.path, source="trade_me", run_id="other")
        self.db.query.assert_not_called()
        self.db.execute.assert_not_called()

    def test_raw_source_must_match_manifest(self):
        self.db.query.return_value.filter.return_value.one.side_effect = ValueError("wrong source")
        with self.assertRaises(ValueError):
            self.loader(self.db, self.path, source="trade_me", run_id="run")
        self.db.execute.assert_not_called()

    def test_only_known_staging_fields_are_written(self):
        self.loader(self.db, self.path, source="trade_me", run_id="run")
        self.statement.values.assert_called_once_with(raw_id="raw-id", job_title="Engineer")
        self.db.commit.assert_called_once()
