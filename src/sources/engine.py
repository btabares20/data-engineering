import hashlib
import json
from urllib.parse import urldefrag, urljoin

from enrichment.descriptions import description_text
from sources.contracts import DEFAULT_LIMITS, FIELDS, json_path, origin, validate_config
from sources.dom import Document, Element, select


def job_postings(data, depth=0):
    if depth > 20:
        raise ValueError("Structured data nesting is too deep")
    if isinstance(data, list):
        for value in data:
            yield from job_postings(value, depth + 1)
    elif isinstance(data, dict):
        types = data.get("@type", [])
        if any(value in ("JobPosting", "https://schema.org/JobPosting", "http://schema.org/JobPosting") for value in (types if isinstance(types, list) else [types])):
            yield data
        else:
            for value in data.values():
                if isinstance(value, (dict, list)):
                    yield from job_postings(value, depth + 1)


def structured_jobs(document):
    for node in select(document.root, 'script[type="application/ld+json"]'):
        try:
            data = json.loads("".join(child for child in node.children if isinstance(child, str)))
        except (ValueError, RecursionError):
            continue
        yield from job_postings(data)


def extract_rule(record, rule):
    if "constant" in rule:
        return rule["constant"]
    if "derive" in rule:
        return None
    if "path" in rule:
        return json_path(record, rule["path"])
    nodes = select(record, rule["selector"])
    if not nodes:
        return None
    node = nodes[0]
    attribute = rule.get("attribute", "text")
    if attribute == "text":
        return node.text()
    if attribute == "html":
        return node.html()
    return node.attrs.get(attribute)


def extract_fields(record, rules, base_url):
    result = {}
    for field, rule in rules.items():
        value = extract_rule(record, rule)
        if value is not None and not isinstance(value, (str, int, float)):
            raise ValueError(f"{field} must extract a scalar; refine its selector or JSON path")
        if value is not None:
            value = str(value).strip() or None
        if field in ("job_url", "attachment", "file_links", "website") and value:
            value = urldefrag(urljoin(base_url, value))[0]
        if field == "job_description":
            value = description_text(value)
        result[field] = value
    return result


class ExtractionEngine:
    def __init__(self, config, fetcher, known=None):
        self.config = validate_config(config)
        self.fetcher = fetcher
        self.known = known or (lambda reference: False)
        self.limits = DEFAULT_LIMITS | config.get("limits", {})
        self.stop_reason = None

    def records(self, page):
        if self.config["mode"] == "json":
            data = json.loads(page.text)
            records = json_path(data, self.config.get("records_path", []))
            if isinstance(records, dict):
                records = [records]
            if not isinstance(records, list):
                raise ValueError("The record path must select a JSON object or array")
            return records, data
        document = Document(page.text)
        if self.config["mode"] == "jsonld":
            return list(structured_jobs(document)), document.root
        return select(document.root, self.config["records_selector"]), document.root

    def crawl(self, max_records=None, max_pages=None):
        record_limit = min(max_records or self.limits["max_records"], self.limits["max_records"])
        page_limit = min(max_pages or self.limits["max_pages"], self.limits["max_pages"])
        url, visited, references = self.config["start_url"], set(), set()
        emitted = examined = 0
        for page_number in range(page_limit):
            if url in visited:
                self.stop_reason = "pagination_loop"
                return
            visited.add(url)
            page = self.fetcher.fetch(url)
            records, document = self.records(page)
            for record in records:
                examined += 1
                if examined > self.limits["max_records"]:
                    self.stop_reason = "max_records"
                    return
                data = {field: None for field in FIELDS - {"external_reference_id"}}
                data.update(extract_fields(record, self.config["fields"], url))
                if not data.get("job_url") or origin(data["job_url"]) != origin(self.config["start_url"]):
                    raise ValueError("Every job URL must remain on the source origin")
                identity_rule = self.config["fields"].get("external_reference_id", {})
                if identity_rule.get("derive") == "job_url_hash":
                    data["external_reference_id"] = hashlib.sha256(data["job_url"].encode()).hexdigest()
                reference = data.get("external_reference_id")
                if not reference:
                    raise ValueError("Every job needs a stable external reference")
                if reference in references:
                    continue
                references.add(reference)
                if self.known(reference):
                    continue
                if self.config.get("detail_fields"):
                    detail = self.fetcher.fetch(data["job_url"])
                    data.update(extract_fields(Document(detail.text).root, self.config["detail_fields"], detail.url))
                data["description_kind"] = data.get("description_kind") or ("full" if data.get("job_description") else "missing")
                yield {"data": data, "listing_url": url, "evidence": record.html()[:20000] if isinstance(record, Element) else record}
                emitted += 1
                if emitted >= record_limit:
                    self.stop_reason = "max_records"
                    return
            pagination = self.config.get("pagination")
            if not pagination:
                self.stop_reason = "no_pagination"
                return
            next_url = extract_rule(document, pagination)
            if not next_url:
                self.stop_reason = "last_page"
                return
            if not isinstance(next_url, str):
                raise ValueError("Pagination must extract a URL string")
            url = urldefrag(urljoin(url, next_url))[0]
        self.stop_reason = "max_pages"
