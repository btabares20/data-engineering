from dataclasses import dataclass
import ipaddress
import socket
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from collection.request_policy import RequestPolicy
from sources.contracts import DEFAULT_LIMITS, origin


class RobotsBlocked(ValueError):
    pass


@dataclass
class Page:
    url: str
    text: str
    content_type: str = "text/html"
    status: int = 200


def public_url(url, expected_origin, resolver=socket.getaddrinfo):
    if origin(url) != expected_origin:
        raise ValueError("Requests must remain on the reviewed source origin")
    host = urlparse(url).hostname
    if host.lower() in ("localhost", "metadata.google.internal") or host.lower().endswith((".localhost", ".local", ".internal")):
        raise ValueError("Only public source hosts are supported")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        addresses = [ipaddress.ip_address(row[4][0]) for row in resolver(host, None)]
    if not addresses or any(not address.is_global for address in addresses):
        raise ValueError("Source host resolved to a nonpublic address")
    return url


class SourceFetcher:
    def __init__(self, config, session=None, policy=None, url_check=public_url):
        import requests
        self.requests = requests
        self.config = config
        self.origin = origin(config["start_url"])
        self.limits = DEFAULT_LIMITS | config.get("limits", {})
        self.session = session or requests.Session()
        self.policy = policy or RequestPolicy(interval=self.limits["interval"])
        self.url_check = url_check
        self.robot_parser = None
        self.robot_status = None
        self.request_count = 0

    def _reserve_request(self):
        if self.request_count >= self.limits["max_requests"]:
            raise ValueError("Source request budget exhausted")
        self.request_count += 1

    def _download(self, url, robots=False):
        self.url_check(url, self.origin)
        response = self.policy.request(
            self.session, "GET", url,
            headers={"User-Agent": self.config["user_agent"], "Accept": "text/html,application/json,text/plain;q=0.8"},
            stream=True,
            before_attempt=self._reserve_request,
            acceptable_statuses=(404, 410) if robots else (),
            retry_exceptions=(self.requests.exceptions.Timeout, self.requests.exceptions.ConnectionError),
        )
        try:
            body = bytearray()
            for chunk in response.iter_content(chunk_size=16384):
                body.extend(chunk)
                if len(body) > self.limits["max_bytes"]:
                    raise ValueError("Source response exceeds the configured byte limit")
            text = bytes(body).decode(response.encoding or "utf-8", errors="replace")
            return Page(url, text, response.headers.get("Content-Type", "").split(";")[0].lower(), response.status_code)
        finally:
            response.close()

    def check_robots(self):
        robots_url = self.origin + "/robots.txt"
        warnings = ["robots.txt is a crawl policy, not legal permission. Review the site's terms and obtain permission where needed."]
        try:
            page = self._download(robots_url, robots=True)
        except Exception as error:
            self.robot_status = {"status": "unavailable", "allowed": False, "url": robots_url,
                                 "warnings": warnings + [f"robots.txt could not be verified ({type(error).__name__}). The website may not allow scraping; do not activate this source yet."]}
            return self.robot_status
        parser = RobotFileParser(robots_url)
        if page.status in (404, 410):
            parser.parse([])
            status = "absent"
            warnings.append("No robots.txt was found. This does not establish permission to scrape.")
        elif page.content_type not in ("text/plain", "") or "<html" in page.text[:500].lower():
            self.robot_status = {"status": "unavailable", "allowed": False, "url": robots_url,
                                 "warnings": warnings + ["robots.txt returned unexpected content. Verify the source's crawl policy before proceeding."]}
            return self.robot_status
        else:
            parser.parse(page.text.splitlines())
            status = "allowed"
        agent = self.config["user_agent"]
        allowed = parser.can_fetch(agent, self.config["start_url"])
        delay = parser.crawl_delay(agent) or parser.crawl_delay("*") or 0
        rate = parser.request_rate(agent) or parser.request_rate("*")
        if rate and rate.requests:
            delay = max(delay, rate.seconds / rate.requests)
        self.policy.interval = max(self.policy.interval, delay)
        self.policy.next_request = max(self.policy.next_request, self.policy.clock() + self.policy.interval)
        if not allowed:
            status = "disallowed"
            warnings.append("robots.txt disallows this URL for this crawler. The website may not allow data scraping; activation is blocked.")
        self.robot_parser = parser
        self.robot_status = {"status": status, "allowed": allowed, "url": robots_url,
                             "user_agent": agent, "interval_seconds": self.policy.interval, "warnings": warnings}
        return self.robot_status

    def fetch(self, url):
        if self.robot_parser is None or not self.robot_status or not self.robot_status["allowed"]:
            raise RobotsBlocked("Verify robots.txt before requesting source content")
        if not self.robot_parser.can_fetch(self.config["user_agent"], url):
            raise RobotsBlocked("robots.txt disallows this listing, detail, or pagination URL")
        return self._download(url)
