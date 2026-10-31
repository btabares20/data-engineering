from email.utils import parsedate_to_datetime
import os
import random
import threading
import time


class RequestPolicy:
    def __init__(self, interval=5.0, retries=2, max_wait=120.0, failure_limit=3,
                 cooldown=300.0, clock=time.monotonic, sleep=time.sleep,
                 wall_clock=time.time, jitter=lambda: random.uniform(0, 1)):
        if interval <= 0 or retries < 0 or max_wait <= 0 or failure_limit <= 0 or cooldown <= 0:
            raise ValueError("Invalid request policy limits")
        self.interval = interval
        self.retries = retries
        self.max_wait = max_wait
        self.failure_limit = failure_limit
        self.cooldown = cooldown
        self.clock = clock
        self.sleep = sleep
        self.wall_clock = wall_clock
        self.jitter = jitter
        self.next_request = 0.0
        self.blocked_until = 0.0
        self.failures = 0
        self.lock = threading.Lock()

    def retry_delay(self, response, attempt):
        header = response.headers.get("Retry-After") if response is not None else None
        if header:
            try:
                delay = max(0, float(header))
            except ValueError:
                try:
                    delay = max(0, parsedate_to_datetime(header).timestamp() - self.wall_clock())
                except (ValueError, TypeError, OverflowError):
                    delay = 2 ** (attempt + 1)
        else:
            delay = 2 ** (attempt + 1)
        return max(self.interval, delay) + self.jitter()

    def request(self, session, method, url, retry_exceptions=(), **kwargs):
        with self.lock:
            if self.clock() < self.blocked_until:
                raise RuntimeError("Source cooldown is active; retry on a later pipeline run")
            try:
                for attempt in range(self.retries + 1):
                    delay = self.next_request - self.clock()
                    if delay > 0:
                        self.sleep(delay)
                    self.next_request = self.clock() + self.interval + self.jitter()
                    response = None
                    try:
                        response = session.request(method, url, timeout=(10, 30), allow_redirects=False, **kwargs)
                    except retry_exceptions:
                        if attempt == self.retries:
                            raise
                    else:
                        if 300 <= response.status_code < 400:
                            raise RuntimeError("Source redirected the request; update the configured endpoint")
                        if response.status_code not in (429, 500, 502, 503, 504):
                            response.raise_for_status()
                            self.failures = 0
                            return response
                        if attempt == self.retries:
                            self.blocked_until = self.clock() + self.retry_delay(response, attempt)
                            response.raise_for_status()
                    delay = self.retry_delay(response, attempt)
                    if response is not None:
                        response.close()
                    if delay > self.max_wait:
                        self.blocked_until = self.clock() + delay
                        raise RuntimeError("Source requested a long pause; deferring this crawl")
                    self.next_request = max(self.next_request, self.clock() + delay)
            except Exception:
                self.failures += 1
                if self.failures >= self.failure_limit:
                    self.blocked_until = max(self.blocked_until, self.clock() + self.cooldown)
                raise


_policies = {}
_policies_lock = threading.Lock()


def source_policy(source):
    with _policies_lock:
        if source not in _policies:
            interval = float(os.getenv(f"{source.upper()}_REQUEST_INTERVAL", "5"))
            _policies[source] = RequestPolicy(interval=interval)
        return _policies[source]
