from typing import TypedDict
from uuid import UUID
from datetime import date


class StagingRaw(TypedDict):
    id: str 
    raw_id: str 
    source: str
    external_reference_id: str
    job_description: str | None
    description_kind: str | None
    job_title: str
    job_url: str
    employer: str
    location: str | None
    position_type: str | None
    category: str | None
    date_listed: date | str | None
    salary_range: str | None
    closing_date: date | str | None
    attachment: str | None
    file_links: str | None
    website: str | None

class QualityMetrics(TypedDict):
    required_fields: bool
    date_validation: bool
    url_validation: bool
    value_validation: bool

class StepMetrics:
    def __init__(self):
        self.rows_in = 0
        self.rows_out = 0
        self.rows_failed = 0
        self.rows_skipped = 0
