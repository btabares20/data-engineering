from typing import TypedDict
from uuid import UUID
from datetime import date


class StagingRaw(TypedDict):
    id: str 
    raw_id: str 
    source: str
    external_reference_id: str
    job_title: str
    job_url: str
    employer: str
    location: str | None
    position_type: str | None
    category: str | None
    date_listed: date | None
    salary_range: str | None
    closing_date: date | None
    attachment: bool
    file_links: list[str] | None
    website: str | None

class QualityMetrics(TypedDict):
    required_fields: bool
    date_validation: bool
    url_validation: bool
    value_validation: bool

