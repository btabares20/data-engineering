from datetime import date, datetime, timedelta
import re
import math
import unicodedata
from urllib.parse import urljoin, urlparse
from uuid import UUID

from dateutil.parser import parse, isoparse


SOURCE_URLS = {"jobs_govt_nz": "https://jobs.govt.nz/", "trade_me": "https://www.trademe.co.nz/"}
LIMITS = {"source": 100, "external_reference_id": 255, "job_title": 255, "employer": 255, "location": 255, "category": 100}


def normalize_text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Expected text")
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip() or None


def normalize_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("Expected a date")
    value = value.strip()
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    if re.match(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", value):
        return isoparse(value).date()
    return parse(value, dayfirst=True).date()


def normalize_url(value, source):
    value = normalize_text(value)
    if value is None:
        return None
    parsed = urlparse(value)
    if not parsed.scheme and source in SOURCE_URLS:
        if not value.startswith(("/", "jobtools/", "jncustomsearch.")):
            raise ValueError("Expected an absolute URL or source-relative path")
        value = urljoin(SOURCE_URLS[source], value)
        parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Expected an HTTP URL")
    if any(character.isspace() for character in value):
        raise ValueError("URL contains whitespace")
    parsed.port
    return value


def validate_record(data, salary_parser, today=None):
    result = dict(data)
    issues = []
    today = today or date.today()
    for field in ("source", "external_reference_id", "job_title", "employer", "location", "position_type", "category"):
        try:
            result[field] = normalize_text(data.get(field))
        except ValueError:
            result[field] = None
            issues.append(f"{field}:invalid_type")
        if field in ("source", "external_reference_id", "job_title", "employer") and not result[field]:
            issues.append(f"{field}:required")
        if result[field] and field in LIMITS and len(result[field]) > LIMITS[field]:
            issues.append(f"{field}:too_long")
    try:
        UUID(str(data.get("raw_id")))
    except (ValueError, TypeError, AttributeError):
        issues.append("raw_id:invalid_uuid")
    for field in ("date_listed", "closing_date"):
        try:
            result[field] = normalize_date(data.get(field))
        except (ValueError, TypeError, OverflowError):
            result[field] = None
            issues.append(f"{field}:invalid_date")
    listed, closing = result.get("date_listed"), result.get("closing_date")
    if listed and listed > today + timedelta(days=30):
        issues.append("date_listed:future_date")
    if listed and closing and closing < listed:
        issues.append("closing_date:before_listing")
    for field in ("job_url", "website", "attachment", "file_links"):
        try:
            result[field] = normalize_url(data.get(field), result.get("source"))
        except (ValueError, TypeError):
            issues.append(f"{field}:invalid_url")
    try:
        low, high, unit = salary_parser(data.get("salary_range"))
        if low is not None and (not math.isfinite(low) or low < 0 or high is None or not math.isfinite(high) or high < low):
            issues.append("salary_range:invalid_bounds")
        if isinstance(data.get("salary_range"), str) and re.search(r"-\s*\d", data["salary_range"].lstrip()) and data["salary_range"].lstrip().startswith("-"):
            issues.append("salary_range:negative_value")
    except (ValueError, TypeError, AttributeError, OverflowError):
        issues.append("salary_range:invalid_value")
    return result, sorted(set(issues))
