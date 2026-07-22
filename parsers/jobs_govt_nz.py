from bs4 import BeautifulSoup
import re
import json

from db.engine import db_context
from db.mappings import Status
from db.models import Raw
from utils.common import utc_now, pipeline_step
from utils.logging import get_logger 

logger = get_logger(__name__)

source_name = 'jobs_govt_nz'
step_name = f"parser:{source_name}"

@pipeline_step(step_name)
def main(run_id, metrics): # i'm keeping the run_id even if it isn't used
    jobs =[]
    with db_context() as db:
        jobs_failed = 0
        jobs_inserted = 0
        try:
            raws = db.query(Raw).filter(Raw.parsed == False, Raw.source == "jobs_govt_nz").all()
            metrics.rows_in = len(raws)
            for raw in raws:
                data = raw.raw
                soup = BeautifulSoup(str(data), "html.parser")
                details_table = soup.select_one("div[class^='job-details']")

                job_desc_raw = soup.find("div", class_="jobDesc")
                job_desc = ""
                if job_desc_raw:
                    job_desc = re.sub(r'\n+', r'\n',(job_desc_raw.text).strip()) # re.sub removes extra \n (s)

                job = { 
                       "job_title": raw.job_title,
                       "job_url": raw.job_url,
                       "raw_id": str(raw.id)
                }
                if details_table:
                    for row in details_table.find_all('tr'):
                        first_td = row.find_all('td')[0].get_text(strip=True)
                        second_td = row.find_all('td')[1].get_text(strip=True)
                        if any(keyword in first_td for keyword in ("File links", "Attachment")):
                            file_td = row.find_all('td')[1]
                            if file_td:
                                file_link_a = file_td.find('a')
                                second_td = file_link_a["href"] if file_link_a else None
                            else: 
                                second_td = None 
                        job[first_td.lower().replace(":","").replace(" ","_")] = second_td
                jobs.append(job)

            with open('jobs_govt_nz_parsed.json', 'w+') as file:
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

