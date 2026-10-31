import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from collection.request_policy import RequestPolicy
from sources.http import public_url, RobotsBlocked, SourceFetcher
from test_source_engine import config


class SourceHttpTests(unittest.TestCase):
    def setUp(self):
        requests = ModuleType("requests")
        requests.Session = Mock()
        requests.exceptions = SimpleNamespace(Timeout=TimeoutError, ConnectionError=ConnectionError)
        self.modules = patch.dict("sys.modules", {"requests": requests})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.now = 0

        def sleep(delay):
            self.now += delay

        self.policy = RequestPolicy(clock=lambda: self.now, sleep=sleep, jitter=lambda: 0)
        self.session = Mock()
        self.fetcher = SourceFetcher(config(), session=self.session, policy=self.policy,
                                     url_check=lambda url, expected: public_url(url, expected, resolver=lambda *args: [(None, None, None, None, ("93.184.216.34", 0))]))

    def response(self, text, status=200, content_type="text/plain"):
        response = Mock(status_code=status, encoding="utf-8", headers={"Content-Type": content_type})
        response.iter_content.return_value = [text.encode()]
        if status >= 400:
            response.raise_for_status.side_effect = RuntimeError(str(status))
        return response

    def test_disallowed_robots_prevent_content_requests(self):
        self.session.request.return_value = self.response("User-agent: *\nDisallow: /jobs")
        self.assertFalse(self.fetcher.check_robots()["allowed"])
        with self.assertRaises(RobotsBlocked):
            self.fetcher.fetch("https://example.com/jobs")
        self.assertEqual(self.session.request.call_count, 1)

    def test_detail_and_pagination_urls_obey_robots(self):
        self.session.request.return_value = self.response("User-agent: *\nDisallow: /private\nAllow: /jobs")
        self.assertTrue(self.fetcher.check_robots()["allowed"])
        with self.assertRaises(RobotsBlocked):
            self.fetcher.fetch("https://example.com/private/123")
        self.assertEqual(self.session.request.call_count, 1)

    def test_robot_delay_and_request_rate_raise_pacing(self):
        self.session.request.return_value = self.response("User-agent: *\nAllow: /\nCrawl-delay: 7\nRequest-rate: 2/20")
        result = self.fetcher.check_robots()
        self.assertEqual(result["interval_seconds"], 10)
        self.session.request.return_value = self.response("<html>Jobs</html>", content_type="text/html")
        self.fetcher.fetch("https://example.com/jobs")
        self.assertEqual(self.now, 10)

    def test_missing_robots_is_reported_without_implying_permission(self):
        self.session.request.return_value = self.response("Not found", 404)
        result = self.fetcher.check_robots()
        self.assertTrue(result["allowed"])
        self.assertEqual(result["status"], "absent")
        self.assertIn("does not establish permission", " ".join(result["warnings"]))

    def test_unverifiable_or_html_robots_is_not_allowed(self):
        for response in (self.response("Forbidden", 403), self.response("<html>Login</html>", content_type="text/html")):
            self.session.request.return_value = response
            result = self.fetcher.check_robots()
            self.assertFalse(result["allowed"])
            self.assertEqual(result["status"], "unavailable")

    def test_byte_budget_closes_response(self):
        self.fetcher.limits["max_bytes"] = 1024
        response = self.response("x" * 1025)
        self.session.request.return_value = response
        with self.assertRaisesRegex(ValueError, "byte limit"):
            self.fetcher._download("https://example.com/jobs")
        response.close.assert_called_once()

    def test_request_budget_counts_retry_attempts(self):
        self.fetcher.limits["max_requests"] = 2
        self.session.request.return_value = self.response("Unavailable", 503)
        with self.assertRaisesRegex(ValueError, "budget"):
            self.fetcher._download("https://example.com/jobs")
        self.assertEqual(self.session.request.call_count, 2)

    def test_only_public_same_origin_urls_can_be_requested(self):
        with self.assertRaises(ValueError):
            public_url("https://other.example/jobs", "https://example.com")
        for host in ("127.0.0.1", "169.254.169.254", "localhost", "10.1.2.3", "[::1]"):
            with self.assertRaises(ValueError):
                public_url("http://" + host + "/jobs", "http://" + host)
        resolver = lambda *args: [(None, None, None, None, ("10.0.0.1", 0))]
        with self.assertRaisesRegex(ValueError, "nonpublic"):
            public_url("https://example.com/jobs", "https://example.com", resolver)
