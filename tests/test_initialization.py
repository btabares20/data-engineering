import ast
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class InitializationTests(unittest.TestCase):
    def test_model_import_does_not_create_tables(self):
        path = Path(__file__).resolve().parents[1] / "src/db/models.py"
        tree = ast.parse(path.read_text())
        imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        namespace = {"__name__": "db.models"}
        engine = ModuleType("db.engine")
        engine.Base = SimpleNamespace(metadata=Mock())
        sqlalchemy = ModuleType("sqlalchemy")
        sqlalchemy.orm = ModuleType("sqlalchemy.orm")
        sqlalchemy.orm.relationship = Mock()
        sqlalchemy.dialects = ModuleType("sqlalchemy.dialects")
        sqlalchemy.dialects.postgresql = ModuleType("sqlalchemy.dialects.postgresql")
        sqlalchemy.dialects.postgresql.UUID = Mock()
        sqlalchemy.dialects.postgresql.JSONB = Mock()
        for node in imports:
            if isinstance(node, ast.ImportFrom) and node.module == "sqlalchemy":
                for alias in node.names:
                    setattr(sqlalchemy, alias.name, Mock())
        modules = {
            "db.engine": engine,
            "sqlalchemy": sqlalchemy,
            "sqlalchemy.orm": sqlalchemy.orm,
            "sqlalchemy.dialects": sqlalchemy.dialects,
            "sqlalchemy.dialects.postgresql": sqlalchemy.dialects.postgresql,
        }
        body = [node for node in tree.body if not isinstance(node, ast.ClassDef)]
        with patch.dict(sys.modules, modules):
            exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), namespace)
        engine.Base.metadata.create_all.assert_not_called()

    def test_explicit_initialization_creates_schema(self):
        path = Path(__file__).resolve().parents[1] / "src/db/initialize.py"
        tree = ast.parse(path.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
        base = SimpleNamespace(metadata=Mock())
        engine = object()
        namespace = {"Base": base, "engine": engine, "upgrade_job_descriptions": Mock()}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
        namespace["initialize"]()
        base.metadata.create_all.assert_called_once_with(bind=engine)
