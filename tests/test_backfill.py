import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from uuid import uuid4


class BackfillTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "src/enrichment/backfill.py"
        tree = ast.parse(path.read_text())
        node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "backfill_source")
        self.db = Mock()
        self.govt_parser, self.govt_loader = Mock(), Mock()
        self.trade_parser, self.trade_loader = Mock(), Mock()
        self.collector = Mock()
        self.transform = Mock()
        namespace = {
            "uuid4": uuid4, "db_context": lambda: nullcontext(self.db),
            "Raw": SimpleNamespace(source=None),
            "run_jobs_govt_parser": self.govt_parser, "run_jobs_govt_loader": self.govt_loader,
            "run_trade_me_parser": self.trade_parser, "run_trade_me_loader": self.trade_loader,
            "trade_me_collector": self.collector, "run_transform": self.transform,
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        self.backfill = namespace["backfill_source"]

    def test_offline_replay_does_not_create_a_source_client(self):
        self.backfill("jobs_govt_nz")
        self.collector.assert_not_called()
        self.govt_parser.assert_called_once()
        self.govt_loader.assert_called_once_with(self.govt_parser.call_args.args[0])
        self.transform.assert_called_once()

    def test_source_validation_happens_before_database_changes(self):
        with self.assertRaises(ValueError):
            self.backfill("jobs_govt_nz", fetch_missing=True)
        self.db.query.assert_not_called()


class StagingDescriptionTests(unittest.TestCase):
    def parser(self, raw_parser):
        path = Path(__file__).resolve().parents[1] / "src/staging/parsers.py"
        tree = ast.parse(path.read_text())
        node = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "JobsParser")
        self.reject, self.clear = Mock(), Mock()
        namespace = {
            "Parser": object, "LocalStorage": object, "Session": object, "Raw": object,
            "Staging": SimpleNamespace(raw_id=None), "logger": Mock(),
            "record_rejection": self.reject, "clear_rejection": self.clear,
            "staging_file": lambda *args: Path("unused.jsonl"), "write_manifest": Mock(),
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        self.storage, self.db = Mock(), Mock()
        parser = namespace["JobsParser"](raw_parser, self.storage, "trade_me", self.db)
        parser._get_jobs = lambda: [SimpleNamespace(id=uuid4(), job_title="Engineer")]
        return parser

    def test_offline_replay_preserves_existing_full_description(self):
        raw_parser = Mock()
        raw_parser.parse_raw.return_value = {"job_description": "Summary", "description_kind": "summary"}
        parser = self.parser(raw_parser)
        self.db.query.return_value.filter.return_value.one_or_none.return_value = SimpleNamespace(
            job_description="Python required", description_kind="full")
        parser.parse("run")
        rows = self.storage.save.call_args.args[1]
        self.assertEqual(rows[0]["job_description"], "Python required")
        self.assertEqual(rows[0]["description_kind"], "full")

    def test_malformed_raw_records_are_quarantined(self):
        raw_parser = Mock()
        raw_parser.parse_raw.side_effect = ValueError("invalid payload")
        parser = self.parser(raw_parser)
        parser.parse("run")
        self.reject.assert_called_once()
        self.assertEqual(self.reject.call_args.kwargs["stage"], "parse")
        self.assertEqual(self.storage.save.call_args.args[1], [])
