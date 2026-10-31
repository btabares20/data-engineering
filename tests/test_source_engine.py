import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sources.contracts import validate_config
from sources.dom import Document, select
from sources.engine import ExtractionEngine
from sources.http import Page


HTML = '''<html><body><article class="job" data-id="101"><h2>Data Engineer</h2>
<span class="company">Example Ltd</span><a href="/jobs/101">Details</a>
<div class="description"><h3>Essential skills</h3><p>Python and SQL</p></div></article>
<article class="job" data-id="102"><h2>Analyst</h2><span class="company">Example Ltd</span>
<a href="/jobs/102">Details</a></article><a class="next" href="/jobs?page=2">Next</a></body></html>'''


def config():
    return {"version": 1, "source_id": "example_jobs", "name": "Example jobs", "start_url": "https://example.com/jobs",
            "user_agent": "ResearchCrawler/1.0", "mode": "html", "records_selector": "article.job",
            "fields": {"external_reference_id": {"selector": "$", "attribute": "data-id"},
                       "job_title": {"selector": "h2"}, "employer": {"selector": ".company"},
                       "job_url": {"selector": "a", "attribute": "href"},
                       "job_description": {"selector": ".description", "attribute": "html"}}}


class FakeFetcher:
    def __init__(self, pages=None, allowed=True):
        self.pages = pages or {"https://example.com/jobs": Page("https://example.com/jobs", HTML)}
        self.calls = []
        self.allowed = allowed

    def check_robots(self):
        self.calls.append("robots")
        return {"allowed": self.allowed, "status": "allowed" if self.allowed else "disallowed", "warnings": ["Review source terms"]}

    def fetch(self, url):
        self.calls.append(url)
        return self.pages[url]


class EngineTests(unittest.TestCase):
    def test_html_fields_map_to_common_schema(self):
        rows = list(ExtractionEngine(config(), FakeFetcher()).crawl())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["data"]["employer"], "Example Ltd")
        self.assertEqual(rows[0]["data"]["job_url"], "https://example.com/jobs/101")
        self.assertEqual(rows[0]["data"]["job_description"], "Essential skills\nPython and SQL")
        self.assertEqual(rows[0]["data"]["description_kind"], "full")

    def test_json_path_records_and_fields(self):
        spec = config()
        spec.update(mode="json", records_path=["jobs"], fields={
            "external_reference_id": {"path": ["id"]}, "job_title": {"path": ["title"]},
            "employer": {"path": ["company", "name"]}, "job_url": {"path": ["url"]}})
        payload = {"jobs": [{"id": 42, "title": "Engineer", "company": {"name": "Example"}, "url": "/jobs/42"}]}
        fetcher = FakeFetcher({spec["start_url"]: Page(spec["start_url"], json.dumps(payload), "application/json")})
        self.assertEqual(list(ExtractionEngine(spec, fetcher).crawl())[0]["data"]["external_reference_id"], "42")

    def test_jsonld_graph_extraction(self):
        spec = config()
        spec.update(mode="jsonld", fields={"external_reference_id": {"derive": "job_url_hash"},
                    "job_title": {"path": ["title"]}, "employer": {"path": ["hiringOrganization", "name"]}, "job_url": {"path": ["url"]}})
        payload = {"@graph": [{"@type": "JobPosting", "title": "Engineer", "hiringOrganization": {"name": "Example"}, "url": "/jobs/1"}]}
        html = '<script type="application/ld+json">' + json.dumps(payload) + '</script>'
        rows = list(ExtractionEngine(spec, FakeFetcher({spec["start_url"]: Page(spec["start_url"], html)})).crawl())
        self.assertEqual(rows[0]["data"]["job_title"], "Engineer")
        self.assertEqual(len(rows[0]["data"]["external_reference_id"]), 64)

    def test_cached_identity_skips_detail_request(self):
        spec = config()
        spec["detail_fields"] = {"job_description": {"selector": "main", "attribute": "html"}}
        fetcher = FakeFetcher()
        self.assertEqual(list(ExtractionEngine(spec, fetcher, known=lambda reference: True).crawl()), [])
        self.assertEqual(fetcher.calls, [spec["start_url"]])

    def test_detail_page_fields(self):
        spec = config()
        spec["detail_fields"] = {"job_description": {"selector": "main", "attribute": "html"}}
        fetcher = FakeFetcher()
        fetcher.pages["https://example.com/jobs/101"] = Page("https://example.com/jobs/101", "<main>Python required</main>")
        row = next(ExtractionEngine(spec, fetcher).crawl(max_records=1))
        self.assertEqual(row["data"]["job_description"], "Python required")
        self.assertEqual(len(fetcher.calls), 2)

    def test_pagination_loop_is_bounded(self):
        spec = config()
        spec["pagination"] = {"selector": "a.next", "attribute": "href"}
        fetcher = FakeFetcher()
        fetcher.pages["https://example.com/jobs?page=2"] = Page("https://example.com/jobs?page=2", HTML)
        engine = ExtractionEngine(spec, fetcher)
        self.assertEqual(len(list(engine.crawl())), 2)
        self.assertEqual(engine.stop_reason, "pagination_loop")
        self.assertEqual(len(fetcher.calls), 2)

    def test_off_origin_jobs_are_rejected(self):
        fetcher = FakeFetcher()
        fetcher.pages[config()["start_url"]].text = HTML.replace('/jobs/101', 'https://other.example/101')
        with self.assertRaisesRegex(ValueError, "source origin"):
            list(ExtractionEngine(config(), fetcher).crawl())

    def test_unknown_fields_and_executable_hooks_are_rejected(self):
        for extra in ({"python": "print('bad')"}, {"fields": {"unknown": {"constant": "value"}}}):
            spec = config() | extra
            with self.assertRaises(ValueError):
                validate_config(spec)

    def test_limits_and_reserved_source_ids_are_validated(self):
        for update in ({"source_id": "../escape"}, {"source_id": "trade_me"}, {"limits": {"interval": 0}}, {"limits": {"max_pages": 10000}}):
            with self.assertRaises(ValueError):
                validate_config(config() | update)

    def test_css_subset_supports_children_and_attributes(self):
        document = Document(HTML)
        self.assertEqual(len(select(document.root, 'article.job[data-id="101"] > h2')), 1)
        with self.assertRaises(ValueError):
            select(document.root, "h2:contains(password)")
