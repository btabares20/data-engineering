import re
from db.mappings import CURRENCY, SALARY_UNIT_PATTERNS, NUMBER_PATTERN


def normalize_salary_number(value: str) -> str:
    value = value.strip().upper()
    if value.endswith("K"):
        return str(float(value[:-1].replace(",", "")) * 1000)

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

    if (
        salary_unit is None
        and salary_min >= 40_000
        and salary_max >= 40_000
    ):
        salary_unit = "year"

    return salary_min, salary_max, salary_unit
