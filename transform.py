import re
import unicodedata
from types import UnionType
from typing import ContextManager, get_type_hints
from uuid import uuid4

from sqlalchemy import UUID, func, select

from sqlalchemy.dialects.postgresql import insert
from db.engine import db_context
from db.mappings import EMPLOYMENT_KEYWORDS, WORK_SCHEDULE_KEYWORDS, EmploymentType, WorkSchedule
from db.models import Raw, Staging, JobPosting
from db.types import StagingRaw, QualityMetrics


from datetime import date, datetime, timedelta
from dateutil.parser import parse
from urllib.parse import urlparse

ALPHA = r'[^a-zA-Z0-9]'
CURRENCY=r"^[^\d-]+"

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
        print(str(e))
        return None
def clean_string(value: str | None) -> str | None:
    if value is None:
        return None
    value = unicodedata.normalize("NFKC", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value

def normalize_salary_number(value: str) -> str:
    value = value.strip()
    # Edge case: 75.000.00 -> 75000.00
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+\.\d+", value):
        parts = value.split(".")
        value = "".join(parts[:-1]) + "." + parts[-1]

    value = value.replace(",", "")

    return value

def split_salary_range(salary_range: str | None):
    salary_min, salary_max = None, None
    if salary_range is None:
        return salary_min, salary_max

    salary_split = salary_range.strip().split("-")
    if len(salary_split) == 2:
        # remove currency, will always be NZD for now
        if salary_split[0]:
            salary_min = re.sub(CURRENCY,'',salary_split[0].strip())
            salary_min = float(normalize_salary_number(salary_min))
        if salary_split[1]:
            salary_max = re.sub(CURRENCY,'',salary_split[1].strip())
            salary_max = float(salary_max.replace(",",""))
    return salary_min, salary_max

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
    salary_min, salary_max = split_salary_range(data.get("salary_range"))
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
        closing_date=data["closing_date"],
        attachment_url=data["attachment"],
        file_links=data["file_links"],
        website=data["website"]
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
def main():
    with db_context() as db:
        query = select(Staging, Raw.id, Raw.source, Raw.external_reference_id).join(Raw)
        results = db.execute(query)
        for row in results:
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
            metrics = quality_checks(staging_raw)
            if not all(metrics.values()):
                print("Skipping row")
                print(metrics)
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
        db.commit()
if __name__ == "__main__":
    main()
