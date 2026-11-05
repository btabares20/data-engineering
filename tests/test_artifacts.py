import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from storage.local import LocalStorage
from storage.paths import artifact_directory, staging_file, verify_manifest, write_manifest


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        environment = patch.dict("os.environ", {"PIPELINE_DATA_DIR": directory.name})
        environment.start()
        self.addCleanup(environment.stop)

    def test_sources_and_runs_have_distinct_paths(self):
        first = staging_file("trade_me", "scheduled/../../first")
        second = staging_file("trade_me", "second")
        other = staging_file("jobs_govt_nz", "scheduled/../../first")
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertNotIn("..", first.parts)
        with self.assertRaises(ValueError):
            artifact_directory("staging", "../unknown", "first")

    def test_manifest_verifies_run_source_and_content(self):
        path = staging_file("trade_me", "first")
        LocalStorage().save(path, [{"raw_id": "one"}])
        write_manifest(path, "trade_me", "first", 1)
        self.assertEqual(verify_manifest(path, "trade_me", "first")["row_count"], 1)
        with self.assertRaises(ValueError):
            verify_manifest(path, "trade_me", "second")
        with self.assertRaises(ValueError):
            verify_manifest(path, "jobs_govt_nz", "first")
        path.write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            verify_manifest(path, "trade_me", "first")

    def test_failed_write_keeps_previous_complete_file(self):
        path = staging_file("trade_me", "first")
        storage = LocalStorage()
        storage.save(path, [{"old": True}])

        def rows():
            yield {"partial": True}
            raise RuntimeError("parser failed")

        with self.assertRaises(RuntimeError):
            storage.save(path, rows())
        self.assertEqual(json.loads(path.read_text()), {"old": True})
        self.assertEqual(list(path.parent.iterdir()), [path])

    def test_empty_run_has_an_explicit_complete_manifest(self):
        path = staging_file("trade_me", "empty")
        LocalStorage().save(path, [])
        write_manifest(path, "trade_me", "empty", 0)
        self.assertEqual(verify_manifest(path, "trade_me", "empty")["row_count"], 0)
