import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class TransformTests(unittest.TestCase):
    def test_database_error_rolls_back_savepoint_and_preserves_other_rows(self):
        path = Path(__file__).resolve().parents[1] / "src/transformation/transform.py"
        tree = ast.parse(path.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "transform")
        columns = [SimpleNamespace(name="title")]
        model = SimpleNamespace(__table__=SimpleNamespace(columns=columns))
        statement = Mock()
        statement.values.return_value = statement
        statement.on_conflict_do_update.return_value = statement
        query = Mock()
        query.join.return_value = query
        staging = SimpleNamespace(title="Job")
        rows = [(staging, str(index), "source", str(index)) for index in range(3)]
        db = Mock()
        db.execute.side_effect = [rows, None, RuntimeError("constraint violation"), None]
        events = []

        @contextmanager
        def savepoint():
            events.append("begin")
            try:
                yield
            except Exception:
                events.append("rollback")
                raise
            else:
                events.append("release")

        db.begin_nested.side_effect = savepoint
        namespace = {
            "Session": object,
            "select": Mock(return_value=query),
            "Staging": model,
            "Raw": SimpleNamespace(id=None, source=None, external_reference_id=None),
            "StagingRaw": dict,
            "validate_record": lambda data, parser: (data, []),
            "split_salary_range": Mock(),
            "record_rejection": Mock(),
            "clear_rejection": Mock(),
            "transform_data": lambda data: staging,
            "JobPosting": model,
            "insert": Mock(return_value=statement),
            "func": Mock(),
            "logger": Mock(),
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
        namespace["transform"](db)
        self.assertEqual(events, ["begin", "release", "begin", "rollback", "begin", "release"])
        self.assertEqual(db.execute.call_count, 4)
        db.commit.assert_called_once()

    def test_invalid_row_is_quarantined_without_curated_insert(self):
        path = Path(__file__).resolve().parents[1] / "src/transformation/transform.py"
        tree = ast.parse(path.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "transform")
        model = SimpleNamespace(__table__=SimpleNamespace(columns=[]))
        query = Mock()
        query.join.return_value = query
        db = Mock()
        db.execute.return_value = [(SimpleNamespace(), "raw-id", "source", "external-id")]
        reject = Mock()
        transform_data = Mock()
        namespace = {
            "Session": object, "select": Mock(return_value=query), "Staging": model,
            "Raw": SimpleNamespace(id=None, source=None, external_reference_id=None),
            "StagingRaw": dict, "validate_record": lambda data, parser: (data, ["employer:required"]),
            "split_salary_range": Mock(), "record_rejection": reject,
            "transform_data": transform_data, "logger": Mock(),
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
        namespace["transform"](db)
        reject.assert_called_once()
        transform_data.assert_not_called()
        db.execute.assert_called_once()
        db.commit.assert_called_once()
