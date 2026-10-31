from email.utils import formatdate
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from collection.request_policy import RequestPolicy


class RequestPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.waits = []

        def sleep(delay):
            self.waits.append(delay)
            self.now += delay

        self.policy = RequestPolicy(clock=lambda: self.now, sleep=sleep, jitter=lambda: 0, wall_clock=lambda: 0)

    def response(self, status, retry_after=None):
        response = Mock(status_code=status, headers={})
        if retry_after:
            response.headers["Retry-After"] = retry_after
        if status >= 400:
            response.raise_for_status.side_effect = RuntimeError(str(status))
        return response

    def test_spaces_requests(self):
        session = Mock()
        session.request.return_value = self.response(200)
        self.policy.request(session, "GET", "https://source")
        self.policy.request(session, "GET", "https://source")
        self.assertEqual(self.waits, [5])
        self.assertEqual(session.request.call_args.kwargs["timeout"], (10, 30))
        self.assertFalse(session.request.call_args.kwargs["allow_redirects"])

    def test_retry_after_seconds_and_dates(self):
        for header in ("20", formatdate(20, usegmt=True)):
            with self.subTest(header=header):
                self.setUp()
                session = Mock()
                session.request.side_effect = [self.response(429, header), self.response(200)]
                self.policy.request(session, "POST", "https://source")
                self.assertEqual(self.waits, [20])

    def test_long_retry_after_defers_instead_of_retrying_early(self):
        session = Mock()
        session.request.return_value = self.response(429, "600")
        with self.assertRaisesRegex(RuntimeError, "long pause"):
            self.policy.request(session, "GET", "https://source")
        with self.assertRaisesRegex(RuntimeError, "cooldown"):
            self.policy.request(session, "GET", "https://source")
        self.assertEqual(session.request.call_count, 1)

    def test_retries_are_bounded(self):
        session = Mock()
        session.request.return_value = self.response(503)
        with self.assertRaises(RuntimeError):
            self.policy.request(session, "GET", "https://source")
        self.assertEqual(session.request.call_count, 3)

    def test_connection_failures_are_retried(self):
        session = Mock()
        session.request.side_effect = [TimeoutError(), self.response(200)]
        self.policy.request(session, "GET", "https://source", retry_exceptions=(TimeoutError,))
        self.assertEqual(session.request.call_count, 2)

    def test_repeated_failures_open_circuit(self):
        session = Mock()
        session.request.return_value = self.response(403)
        for _ in range(3):
            with self.assertRaises(RuntimeError):
                self.policy.request(session, "GET", "https://source")
        with self.assertRaisesRegex(RuntimeError, "cooldown"):
            self.policy.request(session, "GET", "https://source")
        self.assertEqual(session.request.call_count, 3)
