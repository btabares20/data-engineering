import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sources.contracts import digest
from sources.onboarding import SourceOnboarding
from sources.registry import SourceRegistry
from sources.runtime import ConfiguredParser, collect_source
from sources.__main__ import render_review
from test_source_engine import config, FakeFetcher


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.now = 100000.0
        self.registry = SourceRegistry(directory.name, clock=lambda: self.now)
        self.fetchers = []
        self.allowed = True

        def factory(spec):
            fetcher = FakeFetcher(allowed=self.allowed)
            self.fetchers.append(fetcher)
            return fetcher

        self.onboarding = SourceOnboarding(self.registry, factory, clock=lambda: self.now)

    def prepare(self):
        report = self.onboarding.inspect("example_jobs", "https://example.com/jobs")
        self.assertEqual(report["missing_required_fields"], [])
        self.registry.propose(config())
        preview = self.onboarding.preview("example_jobs")
        self.assertTrue(preview["ready"], preview)
        return preview["config_hash"]

    def test_inspection_checks_robots_before_content_and_does_not_activate(self):
        self.onboarding.inspect("example_jobs", "https://example.com/jobs")
        self.assertEqual(self.fetchers[0].calls[0], "robots")
        self.assertEqual(list(self.registry.active()), [])

    def test_disallowed_site_is_not_sampled(self):
        self.allowed = False
        report = self.onboarding.inspect("example_jobs", "https://example.com/jobs")
        self.assertEqual(self.fetchers[0].calls, ["robots"])
        self.assertFalse(report["robots"]["allowed"])
        self.assertIn("may not allow scraping", report["warnings"][0])
        self.assertIn("Robots status: disallowed", render_review(self.registry, "example_jobs"))

    def test_acceptance_requires_terms_acknowledgment_and_fresh_robots(self):
        fingerprint = self.prepare()
        with self.assertRaisesRegex(ValueError, "reviewer"):
            self.onboarding.accept("example_jobs", fingerprint, "reviewer", False)
        self.allowed = False
        with self.assertRaisesRegex(ValueError, "robots.txt"):
            self.onboarding.accept("example_jobs", fingerprint, "reviewer", True)
        self.assertEqual(list(self.registry.active()), [])

    def test_exact_reviewed_config_is_activated_and_can_be_disabled(self):
        fingerprint = self.prepare()
        accepted = self.onboarding.accept("example_jobs", fingerprint, "reviewer", True)
        self.assertEqual(accepted["config_hash"], fingerprint)
        self.assertEqual(len(list(self.registry.active())), 1)
        self.assertTrue(self.registry.path("example_jobs", f"history/{fingerprint}.json").exists())
        self.registry.disable("example_jobs")
        self.assertEqual(list(self.registry.active()), [])

    def test_edit_after_preview_invalidates_acceptance(self):
        fingerprint = self.prepare()
        edited = config()
        edited["fields"]["employer"] = {"constant": "Different employer"}
        self.registry.propose(edited)
        with self.assertRaisesRegex(ValueError, "changed"):
            self.onboarding.accept("example_jobs", fingerprint, "reviewer", True)

    def test_tampered_accepted_file_is_not_executable(self):
        fingerprint = self.prepare()
        accepted = self.onboarding.accept("example_jobs", fingerprint, "reviewer", True)
        accepted["config"]["limits"] = {"max_pages": 10}
        self.registry.write("example_jobs", "accepted.json", accepted)
        with self.assertRaisesRegex(ValueError, "modified"):
            list(self.registry.active())

    def test_old_preview_needs_rechecking(self):
        fingerprint = self.prepare()
        self.now += 86401
        with self.assertRaisesRegex(ValueError, "24 hours"):
            self.onboarding.accept("example_jobs", fingerprint, "reviewer", True)

    def test_review_screen_does_not_present_stale_samples_as_current(self):
        self.prepare()
        self.registry.propose(config() | {"name": "Changed name"})
        screen = render_review(self.registry, "example_jobs")
        self.assertIn("Preview is stale", screen)
        self.assertNotIn("Preview ready: True", screen)

    def test_harness_cannot_change_origin_without_inspection(self):
        self.prepare()
        edited = config() | {"start_url": "https://different.example/jobs"}
        with self.assertRaisesRegex(ValueError, "origin"):
            self.registry.propose(edited)

    def test_review_screen_shows_mappings_robots_and_samples(self):
        self.prepare()
        screen = render_review(self.registry, "example_jobs")
        for text in ("Proposal hash:", "employer:", "Robots status: allowed", "Example Ltd", "Review source terms"):
            self.assertIn(text, screen)

    def test_collected_data_reaches_the_common_parser_with_provenance(self):
        fingerprint = self.prepare()
        accepted = self.onboarding.accept("example_jobs", fingerprint, "reviewer", True)
        storage = Mock()
        storage.contains.return_value = False
        storage.save.return_value = True
        fetcher = FakeFetcher()
        report = collect_source(accepted, fetcher, storage)
        self.assertEqual(report["saved"], 2)
        self.assertEqual(fetcher.calls[0], "robots")
        saved = storage.save.call_args_list[0].args[0]
        payload = json.loads(saved["raw"])
        self.assertEqual(payload["config_hash"], fingerprint)
        raw = SimpleNamespace(raw=saved["raw"], source="example_jobs", id=uuid4())
        parsed = ConfiguredParser().parse_raw(raw)
        self.assertEqual(parsed["employer"], "Example Ltd")
        self.assertEqual(parsed["job_title"], "Data Engineer")
        self.assertEqual(parsed["raw_id"], str(raw.id))
        self.assertNotIn("external_reference_id", parsed)

    def test_robots_are_rechecked_at_collection(self):
        fingerprint = self.prepare()
        accepted = self.onboarding.accept("example_jobs", fingerprint, "reviewer", True)
        storage = Mock()
        with self.assertRaisesRegex(ValueError, "robots.txt"):
            collect_source(accepted, FakeFetcher(allowed=False), storage)
        storage.save.assert_not_called()
