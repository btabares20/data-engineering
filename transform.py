import re
import unicodedata
from types import UnionType
from typing import ContextManager, get_type_hints
from uuid import uuid4

from sqlalchemy import UUID, func, select

from sqlalchemy.dialects.postgresql import insert
from db.engine import db_context
from db.mappings import EMPLOYMENT_KEYWORDS, WORK_SCHEDULE_KEYWORDS, EmploymentType, WorkSchedule, CURRENCY, SALARY_UNIT_PATTERNS, NUMBER_PATTERN
from db.models import Raw, Staging, JobPosting
from db.types import StagingRaw, QualityMetrics


from datetime import date, datetime, timedelta
from dateutil.parser import parse
from urllib.parse import urlparse
from utils.common import pipeline_step
from utils.logging import get_logger 

logger = get_logger(__name__)

step_name = f"transform"

ALPHA = r'[^a-zA-Z0-9]'

def is_valid_url(url: str | None) -> bool:
    if not url:
        return True  # optional field

    parsed = urlparse(url)
    return bool(parsed.scheme and parsed.netloc)

def parse_date(value: str | None) -> date | None:
    if value is None:
        return None

    value = value.strip()
    if not value:
        return None

    try:
        return parse(value).date()
    except ValueError as e:
        logger.exception(str(e))
        return None
def clean_string(value: str | None) -> str | None:
    if value is None:
        return None
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value

def normalize_salary_number(value: str) -> str:
    value = value.strip().upper()
    # Handle K suffix
    if value.endswith("K"):
        return str(float(value[:-1].replace(",", "")) * 1000)

    # Edge case: 75.000.00 -> 75000.00
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+\.\d+", value):
        parts = value.split(".")
        value = "".join(parts[:-1]) + "." + parts[-1]

    value = value.replace(",", "")

    return value
def split_salary_range(
    salary_range: str | None,
) -> tuple[float | None, float |None, str | None]:
    if not salary_range:
        return None, None, None

    text = salary_range.strip()

    salary_unit = None
    for unit, pattern in SALARY_UNIT_PATTERNS.items():
        if pattern.search(text):
            salary_unit = unit
            break

    numbers = NUMBER_PATTERN.findall(re.sub(CURRENCY, "", text))

    if not numbers:
        return None, None, salary_unit

    parsed = [float(normalize_salary_number(n)) for n in numbers]

    salary_min = parsed[0]
    salary_max = parsed[1] if len(parsed) > 1 else parsed[0]

    # Legacy heuristic: large salaries without an explicit unit
    if (
        salary_unit is None
        and salary_min >= 40_000
        and salary_max >= 40_000
    ):
        salary_unit = "year"

    return salary_min, salary_max, salary_unit

def normalize_position_type(position_type: str | None):
    if position_type is None:
        return None, None
    normalized = re.sub(ALPHA, ' ', position_type.strip()).lower()
    normalized = re.sub(r' +', r' ',(normalized).strip())
    position_keywords = normalized.split()
    employment_type = EmploymentType.UNKNOWN
    work_schedule = WorkSchedule.UNKNOWN
    for enum, keywords in EMPLOYMENT_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            employment_type = enum
            break
    for enum, keywords in WORK_SCHEDULE_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            work_schedule = enum
            break
    return employment_type.value , work_schedule.value


def transform_data(data: StagingRaw):
    salary_min, salary_max, salary_unit = split_salary_range(data.get("salary_range"))
    employment_type, work_schedule = normalize_position_type(data.get("position_type"))
    return JobPosting(
        source=data["source"],
        external_reference_id=data["external_reference_id"],
        title=clean_string(data["job_title"]),
        employer=clean_string(data["employer"]),
        location=clean_string(data["location"]),
        employment_type=employment_type,
        work_schedule=work_schedule,
        category=data["category"],
        date_listed=data["date_listed"],
        salary_min=salary_min,
        salary_max=salary_max,
        salary_unit=salary_unit,
        closing_date=data["closing_date"],
        attachment_url=data["attachment"],
        file_links=data["file_links"],
        website=data["website"],
        job_url=data["job_url"]
    )

    

def quality_checks(data: StagingRaw) -> QualityMetrics:
    metrics: QualityMetrics = {
        "required_fields": True,
        "date_validation": True,
        "url_validation": True,
        "value_validation": True,
    }

    if (
        data["raw_id"] is None
        or data["source"] is None
        or data["external_reference_id"] is None
        or data["job_title"] is None
        or not data["job_title"].strip()
    ):
        metrics["required_fields"] = False

    today = date.today()
    date_listed = parse_date(data["date_listed"])
    closing_date = parse_date(data["closing_date"])

    if data["date_listed"] is not None and date_listed is None:
        metrics["date_validation"] = False

    if data["closing_date"] is not None and closing_date is None:
        metrics["date_validation"] = False

    if (
        date_listed is not None
        and closing_date is not None
        and closing_date < date_listed
    ):
        metrics["date_validation"] = False

    if (
        date_listed is not None
        and date_listed > today + timedelta(days=30)
    ):
        metrics["date_validation"] = False

    for field in (
        "employer",
        "location",
        "position_type",
    ):
        value = data[field]
        if value is not None and not value.strip():
            metrics["value_validation"] = False
            break

    return metrics 

@pipeline_step(step_name)
def main(run_id, decorator_metrics):
    with db_context() as db:
        query = select(Staging, Raw.id, Raw.source, Raw.external_reference_id).join(Raw)
        results = db.execute(query)
        for row in results:
            decorator_metrics.rows_in += 1
            staging_fields: Staging = row[0]
            raw_id: str = row[1]
            source: str = row[2]
            external_reference_id: str = row[3]
            staging_raw: StagingRaw= StagingRaw(
                **{
                    c.name: getattr(staging_fields, c.name)
                    for c in Staging.__table__.columns
                },
                source = source,
                external_reference_id= external_reference_id)
            try:
                metrics = quality_checks(staging_raw)
                if not all(metrics.values()):
                    logger.info("Skipping row")
                    logger.info(metrics)
                    decorator_metrics.rows_skipped +=1
                    continue
                job = transform_data(staging_raw)
                values = {
                    c.name: getattr(job, c.name)
                    for c in JobPosting.__table__.columns
                    if c.name not in {"id", "created_at", "updated_at"}
                }
                stmt = insert(JobPosting).values(**values)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_job_postings_source_external_ref",
                    set_={
                        key: getattr(stmt.excluded, key)
                        for key in values.keys()
                        if key not in {"source", "external_reference_id"}
                    }
                    | {"updated_at": func.now()}
                )
                db.execute(stmt)
                decorator_metrics.rows_out += 1
            except Exception as e:
                decorator_metrics.rows_failed += 1
                logger.exception(f"Failed row {raw_id}: {e}")
                continue
        db.commit()
