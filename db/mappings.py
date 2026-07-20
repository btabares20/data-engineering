from enum import StrEnum 

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
    EmploymentType.PERMANENT: {"permanent"},
    EmploymentType.ONGOING: {"ongoing", "on-going"},
    EmploymentType.FIXED_TERM: {"fixed term", "fixedterm"},
    EmploymentType.TEMPORARY: {"temporary", "temp"},
    EmploymentType.CASUAL: {"casual"},
    EmploymentType.SECONDMENT: {"secondment"},
}

class WorkSchedule(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    UNKNOWN = "unknown"

WORK_SCHEDULE_KEYWORDS = {
    WorkSchedule.FULL_TIME: {"full time", "fulltime", "full-time"},
    WorkSchedule.PART_TIME: {"part time", "parttime", "part-time"},
}
