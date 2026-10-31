import ast
import asyncio
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class OrchestratorTests(unittest.TestCase):
    def test_collector_failure_propagates_to_caller(self):
        path = Path(__file__).resolve().parents[1] / "src/orchestrator.py"
        tree = ast.parse(path.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "main")
        parser = Mock()
        transform = Mock()

        async def to_thread(function):
            return function()

        namespace = {
            "asyncio": SimpleNamespace(gather=asyncio.gather, to_thread=to_thread),
            "db_context": nullcontext,
            "logger": Mock(),
            "run_jobs_govt_collector": Mock(side_effect=RuntimeError("collection failed")),
            "run_trade_me_collector": Mock(),
            "run_jobs_govt_parser": parser,
            "run_trade_me_parser": parser,
            "run_jobs_govt_loader": Mock(),
            "run_trade_me_loader": Mock(),
            "run_transform": transform,
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), "exec"), namespace)
        with self.assertRaisesRegex(RuntimeError, "collection failed"):
            asyncio.run(namespace["main"]())
        parser.assert_not_called()
        transform.assert_not_called()
