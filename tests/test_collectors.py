import ast
from datetime import datetime
import json
import math
from pathlib import Path
import random
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


def collector_types():
    path = Path(__file__).resolve().parents[1] / "src/collection/collectors.py"
    tree = ast.parse(path.read_text())
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    namespace = dict(globals())
    namespace.update(
        Collector=object,
        TradeMeClient=object,
        TradeMeRawParser=object,
        JobsGovtClient=object,
        JobsGovtRawParser=object,
        PostgreSQLRawStorage=object,
        logger=Mock(),
    )
    exec(compile(ast.Module(body=classes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


class TradeMeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.pages = []
        self.storage = Mock()
        self.client = SimpleNamespace(base_params={"rows": 1}, get_listings=self.get_listings)
        parser = SimpleNamespace(parse_job_count=lambda data: 5, _get_category_name=lambda *args: "IT")
        self.collector = collector_types()["TradeMeCollector"](self.client, parser, self.storage)
        self.collector.output_dir = Path(self.directory.name)
        self.collector._short_sleep = lambda: None
        self.collector._long_sleep = lambda: None

    def get_listings(self, page, region):
        self.pages.append(page)
        return {
            "TotalCount": 5,
            "FoundCategories": [],
            "List": [{"Category": "1-2-", "ListingId": page, "CanonicalPath": "/job", "Title": "Job"}],
        }

    def test_populated_pages_do_not_stop_collection(self):
        jobs = self.collector.collect_region("wellington")
        self.assertEqual(self.pages, [1, 2, 3, 4, 5])
        self.assertEqual(len(jobs), 5)

    def test_populated_page_resets_empty_page_counter(self):
        original = self.client.get_listings

        def get_listings(page, region):
            data = original(page, region)
            if page in (1, 3):
                data["List"] = []
            return data

        self.client.get_listings = get_listings
        self.collector.collect_region("wellington")
        self.assertEqual(self.pages, [1, 2, 3, 4, 5])

    def test_two_empty_pages_stop_collection(self):
        original = self.client.get_listings

        def get_listings(page, region):
            data = original(page, region)
            data["List"] = []
            return data

        self.client.get_listings = get_listings
        self.collector.collect_region("wellington")
        self.assertEqual(self.pages, [1, 2])

    def test_failed_write_retries_uncommitted_page(self):
        self.storage.save.side_effect = [True, RuntimeError("database unavailable")]
        with self.assertRaises(RuntimeError):
            self.collector.collect_region("wellington")
        self.assertEqual(self.collector.get_resume_page("wellington"), 2)
        self.storage.save.side_effect = None
        self.pages.clear()
        self.collector.collect_region("wellington")
        self.assertEqual(self.pages, [2, 3, 4, 5])
        self.assertIsNone(self.collector.get_resume_page("wellington"))

    def test_legacy_files_do_not_skip_unsaved_jobs(self):
        today = datetime.now().strftime("%Y%m%d")
        for suffix in (".json", "_END.json"):
            path = self.collector.output_dir / f"trademe_jobs_page_wellington_5_{today}_120000{suffix}"
            path.write_text("{}")
        self.assertEqual(self.collector.get_resume_page("wellington"), 1)

    def test_partial_checkpoint_does_not_advance_resume(self):
        today = datetime.now().strftime("%Y%m%d")
        path = self.collector.output_dir / f"trademe_jobs_page_wellington_1_{today}_120000_COMMITTED.tmp"
        path.write_text("{")
        self.assertEqual(self.collector.get_resume_page("wellington"), 1)
