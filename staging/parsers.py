import json
import re
from bs4 import BeautifulSoup
from db.models import Raw
from staging.base import Parser
from utils.common import dotnet_date_to_string
from sqlalchemy.orm import Session
from storage.local import LocalStorage


class JobsGovtParser(Parser):
    def parse_raw(self, raw: Raw)->dict:
        data = raw.raw
        soup = BeautifulSoup(str(data), "html.parser")
        details_table = soup.select_one("div[class^='job-details']")

        job_desc_raw = soup.find("div", class_="jobDesc")
        job_desc = ""
        if job_desc_raw: # still not saving this, too lazy to change the schema
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
        return job

class TradeMeParser(Parser):
    def parse_raw(self, raw: Raw)->dict:
        data = json.loads(str(raw.raw))
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

        return job

class JobsParser:
    def __init__(self, parser: Parser, storage: LocalStorage, source: str, db: Session) -> None:
        self.parser = parser
        self.storage = storage
        self.source = source
        self.db = db

    def _get_jobs(self):
        raws = self.db.query(Raw).filter(Raw.parsed == False, Raw.source == self.source).all()
        return raws

    def parse(self):
        return
        jobs = []
        raws = self._get_jobs()
        for raw in raws:
            job = self.parser.parse_raw(raw)
            jobs.append(jobs)

        self.storage.save(f"{self.source}_parsed.json", jobs)
