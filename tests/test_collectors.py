import ast
from datetime import datetime
import json
import math
from pathlib import Path
import sys
import random
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from storage.paths import artifact_directory


def collector_types():
    path = Path(__file__).resolve().parents[1] / "src/collection/collectors.py"
    tree = ast.parse(path.read_text())
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    namespace = dict(globals())
    namespace.update(
        Collector=object,
        artifact_directory=artifact_directory,
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
        self.storage.contains.return_value = False
        self.client = SimpleNamespace(base_params={"rows": 1}, get_listings=self.get_listings, get_job_details=Mock(return_value={"Body": "Python required"}))
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

    def test_known_listings_skip_details_without_stopping_pagination(self):
        self.storage.contains.return_value = True
        self.collector.collect_region("wellington")
        self.assertEqual(self.pages, [1, 2, 3, 4, 5])
        self.client.get_job_details.assert_not_called()
        self.storage.save.assert_not_called()

    def test_new_listing_details_are_retained_in_raw_storage(self):
        self.collector.collect_region("wellington")
        payload = json.loads(self.storage.save.call_args.args[0]["raw"])
        self.assertEqual(payload["DescriptionBody"], "Python required")
        self.assertEqual(self.client.get_job_details.call_count, 5)


class JobsGovtTests(unittest.TestCase):
    def test_duplicate_page_does_not_hide_later_unseen_jobs(self):
        client = Mock()
        client.get_listing_page.side_effect = ["first page", "second page"]
        client.get_job_page.return_value = "details"
        parser = Mock()
        parser.parse_job_count.return_value = 40
        parser.parse_listings.side_effect = [
            [{"job_url": "/known", "job_title_text": "Known"}],
            [{"job_url": "/new", "job_title_text": "New"}],
        ]
        parser.parse_details.return_value = {"external_reference_id": "reference", "raw": "details"}
        storage = Mock()
        storage.contains_url.return_value = False
        storage.save.side_effect = [False, True]
        collector = collector_types()["JobsGovtCollector"](client, parser, storage)
        collector.collect()
        self.assertEqual(client.get_listing_page.call_count, 2)
        self.assertEqual(storage.save.call_count, 2)

    def test_empty_results_end_pagination_without_a_count(self):
        client = Mock()
        parser = Mock()
        parser.parse_job_count.return_value = 0
        parser.parse_listings.return_value = []
        storage = Mock()
        storage.contains_url.return_value = False
        collector = collector_types()["JobsGovtCollector"](client, parser, storage)
        collector.collect()
        client.get_listing_page.assert_called_once_with("0")
        storage.save.assert_not_called()
