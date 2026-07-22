
from datetime import datetime
import json
import re

from db.engine import db_context
from db.mappings import EMPLOYMENT_KEYWORDS
from db.models import Raw
from utils.common import pipeline_step
from utils.logging import get_logger 

logger = get_logger(__name__)

source_name = 'trade_me'
step_name = f"parser:{source_name}"

def dotnet_date_to_string(value: str | None, fmt: str = "%d-%b-%Y") -> str | None:
    if not value:
        return None
    match = re.search(r"\d+", value)
    if not match:
        return None
    milliseconds = int(match.group())
    return datetime.fromtimestamp(milliseconds / 1000).strftime(fmt)

@pipeline_step(step_name)
def main(run_id, metrics):
    jobs =[]
    jobs_failed = 0
    jobs_inserted = 0
    with db_context() as db:
        try:
            raws = db.query(Raw).filter(Raw.parsed == False, Raw.source == source_name).all()
            for raw in raws:
                metrics.rows_in = len(raws)
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
                    try:
                        file.write(json.dumps(job) + "\n")
                        jobs_inserted += 1
                    except Exception:
                        jobs_failed += 1
        except Exception as e:
            logger.exception(str(e))
            raise
        finally:
            metrics.rows_out = jobs_inserted
            metrics.rows_failed = jobs_failed

