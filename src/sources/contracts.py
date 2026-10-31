import hashlib
import json
import math
import re
from urllib.parse import urlparse

from sources.dom import selector_steps


FIELDS = {"external_reference_id", "job_title", "employer", "location", "position_type", "category", "date_listed", "salary_range", "closing_date", "attachment", "file_links", "website", "job_url", "job_description", "description_kind"}
REQUIRED = {"external_reference_id", "job_title", "employer", "job_url"}
SOURCE_ID = re.compile(r"[a-z][a-z0-9_]{2,63}")
DEFAULT_LIMITS = {"interval": 5, "max_pages": 5, "max_records": 100, "max_requests": 120, "max_bytes": 1048576}


def source_id(value):
    if not isinstance(value, str) or not SOURCE_ID.fullmatch(value):
        raise ValueError("Source ID must be 3–64 lowercase letters, digits, or underscores")
    return value


def origin(url):
    if not isinstance(url, str) or not url or len(url) > 2048 or any(ord(character) < 32 for character in url):
        raise ValueError("Use a bounded HTTP(S) URL without control characters")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Use an HTTP(S) URL without embedded credentials")
    if parsed.port not in (None, 80 if parsed.scheme == "http" else 443):
        raise ValueError("Only standard HTTP(S) ports are supported")
    host = parsed.hostname.lower()
    host = f"[{host}]" if ":" in host else host
    return f"{parsed.scheme}://{host}"


def digest(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def validate_path(path):
    if not isinstance(path, list) or len(path) > 12 or any(type(part) not in (str, int) or (isinstance(part, int) and part < 0) for part in path):
        raise ValueError("JSON paths must be bounded lists of keys or nonnegative indexes")


def validate_rule(rule, mode, field):
    if not isinstance(rule, dict) or set(rule) - {"selector", "attribute", "path", "constant", "derive"}:
        raise ValueError(f"Invalid extraction rule for {field}")
    kinds = set(rule) & {"selector", "path", "constant", "derive"}
    if len(kinds) != 1:
        raise ValueError("Each rule must use exactly one selector, path, constant, or derivation")
    if "selector" in rule:
        if mode not in ("html", "detail"):
            raise ValueError("Selectors apply to HTML records")
        selector_steps(rule["selector"])
        attribute = rule.get("attribute", "text")
        if not isinstance(attribute, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", attribute):
            raise ValueError("Invalid HTML attribute")
    elif "attribute" in rule:
        raise ValueError("Attributes require an HTML selector")
    if "path" in rule:
        if mode not in ("json", "jsonld"):
            raise ValueError("JSON paths apply to JSON records")
        validate_path(rule["path"])
    if "constant" in rule and (rule["constant"] is not None and not isinstance(rule["constant"], (str, int, float))):
        raise ValueError("Constants must be scalar values")
    if "derive" in rule and (field != "external_reference_id" or rule["derive"] != "job_url_hash"):
        raise ValueError("Only job_url_hash identity derivation is supported")


def validate_config(config):
    if not isinstance(config, dict) or set(config) - {"version", "source_id", "name", "start_url", "user_agent", "mode", "records_selector", "records_path", "fields", "detail_fields", "pagination", "limits"}:
        raise ValueError("Unknown source configuration keys")
    if type(config.get("version")) is not int or config.get("version") != 1 or config.get("mode") not in ("html", "json", "jsonld"):
        raise ValueError("Use configuration version 1 and html, json, or jsonld mode")
    source_id(config.get("source_id"))
    if config["source_id"] in ("trade_me", "jobs_govt_nz"):
        raise ValueError("Built-in source identifiers are reserved")
    origin(config.get("start_url", ""))
    if not isinstance(config.get("name"), str) or not 1 <= len(config["name"]) <= 100:
        raise ValueError("A source display name is required")
    agent = config.get("user_agent", "")
    if not isinstance(agent, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,60}/[0-9.]+", agent):
        raise ValueError("Use an identifiable Product/version user agent")
    if config["mode"] == "html":
        selector_steps(config.get("records_selector", ""))
    elif config["mode"] == "json":
        validate_path(config.get("records_path", []))
    fields, details = config.get("fields"), config.get("detail_fields", {})
    if not isinstance(fields, dict) or not isinstance(details, dict) or (set(fields) | set(details)) - FIELDS:
        raise ValueError("Map only fields from the common job schema")
    if not REQUIRED <= (set(fields) | set(details)):
        raise ValueError("Map identity, title, employer, and job URL before previewing")
    if details and not {"external_reference_id", "job_url", "job_title"} <= set(fields):
        raise ValueError("Detail fetching requires listing-page identity, title, and URL mappings")
    if set(details) & {"external_reference_id", "job_url"}:
        raise ValueError("Details cannot change a listing's identity or URL")
    for name, rule in fields.items():
        validate_rule(rule, config["mode"], name)
    for name, rule in details.items():
        validate_rule(rule, "detail", name)
    pagination = config.get("pagination", {})
    if not isinstance(pagination, dict) or set(pagination) - {"selector", "attribute", "path"}:
        raise ValueError("Invalid pagination mapping")
    if pagination:
        validate_rule(pagination, "json" if config["mode"] == "json" else "html", "pagination")
    if not isinstance(config.get("limits", {}), dict):
        raise ValueError("Limits must be an object")
    limits = DEFAULT_LIMITS | config.get("limits", {})
    if set(limits) != set(DEFAULT_LIMITS):
        raise ValueError("Unknown request limit")
    for key, value in limits.items():
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Limits must be finite numbers")
        low, high = {"interval": (1, 3600), "max_pages": (1, 100), "max_records": (1, 1000), "max_requests": (2, 1000), "max_bytes": (1024, 2097152)}[key]
        if not low <= value <= high or (key != "interval" and type(value) is not int):
            raise ValueError(f"Invalid {key} limit")
    digest(config)
    return config


def json_path(data, path):
    for part in path:
        try:
            data = data[part]
        except (KeyError, IndexError, TypeError):
            return None
    return data
