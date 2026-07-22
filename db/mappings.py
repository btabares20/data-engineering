from enum import StrEnum 
import re

class EmploymentType(StrEnum):
    PERMANENT = "permanent"
    FIXED_TERM = "fixed_term"
    TEMPORARY = "temporary"
    CASUAL = "casual"
    SECONDMENT = "secondment"
    CONTRACT = "contract"
    ONGOING = "ongoing"
    UNKNOWN = "unknown"

EMPLOYMENT_KEYWORDS = {
    EmploymentType.PERMANENT: {"permanent","per"},
    EmploymentType.FIXED_TERM: {"fixed term", "fixedterm"},
    EmploymentType.TEMPORARY: {"temporary", "temp"},
    EmploymentType.CASUAL: {"casual"},
    EmploymentType.SECONDMENT: {"secondment"},
    EmploymentType.CONTRACT: {"contract", "ct"},
    EmploymentType.ONGOING: {"ongoing", "on-going"},
}

class WorkSchedule(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    UNKNOWN = "unknown"

WORK_SCHEDULE_KEYWORDS = {
    WorkSchedule.FULL_TIME: {"full time", "fulltime", "full-time", "ft"},
    WorkSchedule.PART_TIME: {"part time", "parttime", "part-time", "pt"},
}

class SalaryUnit(StrEnum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    UNKNOWN = "unknown"

CURRENCY = re.compile(r"(NZ\$|\$)", re.IGNORECASE)
CURRENCY = re.compile(r"(NZ\$|\$)", re.IGNORECASE)

NUMBER_PATTERN = re.compile(
    r"\d+(?:[.,]\d+)*(?:K)?",
    re.IGNORECASE,
)

SALARY_UNIT_PATTERNS = {
    "hour": re.compile(r"\b(hour|hr|hourly|per hour)\b", re.IGNORECASE),
    "day": re.compile(r"\b(day|daily|per day)\b", re.IGNORECASE),
    "week": re.compile(r"\b(week|weekly|per week)\b", re.IGNORECASE),
    "month": re.compile(r"\b(month|monthly|per month)\b", re.IGNORECASE),
    "year": re.compile(
        r"\b(year|yearly|annual|annually|per annum|pa)\b",
        re.IGNORECASE,
    ),
}

class Status(StrEnum):
    STARTED = "STARTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

PIPELINE="nz-jobs"
TRIGGER="manual"

