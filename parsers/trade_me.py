
from datetime import datetime
import json
import re

from db.engine import db_context
from db.mappings import EMPLOYMENT_KEYWORDS
from db.models import Raw

source_name = 'trade_me'

def dotnet_date_to_string(value: str | None, fmt: str = "%d-%b-%Y") -> str | None:
    if not value:
        return None
    match = re.search(r"\d+", value)
    if not match:
        return None
    milliseconds = int(match.group())
    return datetime.fromtimestamp(milliseconds / 1000).strftime(fmt)

def main():
    jobs =[]
    with db_context() as db:
        raws = db.query(Raw).filter(Raw.parsed == False, Raw.source == source_name).all()
        for raw in raws:
            data = json.loads(raw.raw)
            is_transparent = data["JobsSalaryTransparency"]["HasOptedIn"]
            if is_transparent:
                salary_range = data["JobsSalaryTransparency"]["ApproximatePayRangeDisplay"]
            else:
                salary_range = " - "
            employer = data["Agency"].get("Name", None) if data.get("Agency") else None
            if not employer:
                employer = data["Company"]
            job = { 
                   "job_title": raw.job_title,
                   "job_url": raw.job_url,
                   "raw_id": str(raw.id),
                   "employer": employer, 
                   "location": data["JobLocation"], 
                   "position_type": f"{data['ContractLength']} - {data["JobType"]}",
                   "category": data["CategoryName"],
                   "date_listed": dotnet_date_to_string(data["StartDate"]),
                   "closing_date": dotnet_date_to_string(data["EndDate"]),
                   "salary_range": salary_range
            }
            jobs.append(job)

        with open('trade_me_parsed.json', 'w+') as file:
            for job in jobs:
                file.write(json.dumps(job) + "\n")

if __name__ == "__main__":
    main()
