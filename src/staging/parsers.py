import json
import re
from bs4 import BeautifulSoup
from db.models import Raw, Staging
from staging.base import Parser
from utils.common import dotnet_date_to_string
from sqlalchemy.orm import Session
from storage.local import LocalStorage
from storage.paths import staging_file, write_manifest
from enrichment.descriptions import description_text, trademe_description
from transformation.quality_storage import record_rejection, clear_rejection
from utils.logging import get_logger

logger = get_logger(__name__)


class JobsGovtParser(Parser):
    def parse_raw(self, raw: Raw)->dict:
        data = raw.raw
        soup = BeautifulSoup(str(data), "html.parser")
        details_table = soup.select_one("div[class^='job-details']")

        job_desc_raw = soup.find("div", class_="jobDesc")
        job_desc = description_text(str(job_desc_raw)) if job_desc_raw else None

        job = { 
               "job_title": raw.job_title,
           "job_description": description,
           "description_kind": description_kind,
               "job_description": job_desc,
               "description_kind": "full" if job_desc else "missing",
               "job_url": raw.job_url,
               "raw_id": str(raw.id)
        }

        if details_table:
            for row in details_table.find_all('tr'):
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                first_td = cells[0].get_text(strip=True)
                second_td = cells[1].get_text(strip=True)
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
        description, description_kind = trademe_description(data)
        transparency = data.get("JobsSalaryTransparency") or {}
        is_transparent = transparency.get("HasOptedIn", False)
        if is_transparent:
            salary_range = transparency.get("ApproximatePayRangeDisplay")
        else:
            salary_range = " - "
        employer = data["Agency"].get("Name", None) if data.get("Agency") else None
        if not employer:
            employer = data.get("Company")
        job = { 
           "job_title": raw.job_title,
           "job_description": description,
           "description_kind": description_kind,
           "job_url": raw.job_url,
           "raw_id": str(raw.id),
           "employer": employer, 
           "location": data.get("JobLocation"), 
           "position_type": f"{data.get('ContractLength', '')} - {data.get('JobType', '')}",
           "category": data.get("CategoryName"),
           "date_listed": dotnet_date_to_string(data.get("StartDate")),
           "closing_date": dotnet_date_to_string(data.get("EndDate")),
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

    def parse(self, run_id):
        jobs = []
        raws = self._get_jobs()
        for raw in raws:
            logger.info(f"{self.parser.__class__.__name__}: Parsing {raw.job_title}")
            try:
                job = self.parser.parse_raw(raw)
            except (ValueError, KeyError, TypeError, IndexError) as error:
                record_rejection(self.db, {"raw_id": str(raw.id), "source": self.source}, [f"parse:{type(error).__name__}"], stage="parse")
                continue
            if job.get("description_kind") != "full":
                existing = self.db.query(Staging).filter(Staging.raw_id == raw.id).one_or_none()
                if existing is not None and existing.description_kind == "full" and existing.job_description:
                    job["job_description"] = existing.job_description
                    job["description_kind"] = "full"
            clear_rejection(self.db, raw.id, stage="parse")
            jobs.append(job)

        path = staging_file(self.source, run_id)
        self.storage.save(path, jobs)
        write_manifest(path, self.source, run_id, len(jobs))
        self.db.commit()
        return path
