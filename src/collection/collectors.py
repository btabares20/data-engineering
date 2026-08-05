from datetime import datetime
import json
import math
from pathlib import Path
import random
import re
import time
from typing import Any
from bs4 import BeautifulSoup
from collection.clients import JobsGovtClient, TradeMeClient
from collection.parsers import JobsGovtRawParser, TradeMeRawParser
from storage.postgres import PostgreSQLRawStorage
from collection.base import Collector
from utils.logging import get_logger

logger = get_logger(__name__)

class TradeMeCollector(Collector):
    def __init__(self, 
        client: TradeMeClient, 
        parser: TradeMeRawParser, 
        storage: PostgreSQLRawStorage,
    ) -> None:
        self.source = "trade_me"
        self.client = client
        self.parser = parser 
        self.storage = storage
        self.output_dir = Path(f"raw_data/{self.source}")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_resume_page(self, region) -> int:
        today = datetime.now().strftime("%Y%m%d")
        # Already finished today?
        end_files = sorted(
            self.output_dir.glob(f"trademe_jobs_page_{region}_*_{today}_*_END.json")
        )
        if end_files:
            raise RuntimeError(
                f"Today's crawl has already completed ({end_files[-1].name})."
            )
        pattern = re.compile(
            rf"trademe_jobs_page_{region}_(\d+)_{today}_\d{{6}}\.json"
        )
        latest_page = 0
        for file in self.output_dir.glob(f"trademe_jobs_page_{region}_*.json"):
            match = pattern.match(file.name)
            if match:
                latest_page = max(latest_page, int(match.group(1)))
        return latest_page + 1

    def _short_sleep(self): 
        seconds = random.uniform(2.5, 6.5)
        logger.info(f"Sleeping {seconds:.1f}s...")
        time.sleep(seconds)


    def _long_sleep(self):
        seconds = random.uniform(60, 120)
        logger.info(f"Long break for {seconds:.0f}s...")
        time.sleep(seconds)
    
    def collect_region(self, region)->list[dict]:
        logger.info(f"starting trade_me scraper region: {region}")
        page = self.get_resume_page(region)
        requests_until_long_sleep = random.randint(3, 6)
        requests_since_long_sleep = 0
        total_jobs = None
        last_page = None
        page_since_last_new_job = 0
        
        jobs = []
        while last_page is None or page <= last_page:
            found_new_job = 0
            listings_raw = self.client.get_listings(page, region)
            categories = listings_raw["FoundCategories"]
            if total_jobs is None:
                total_jobs = self.parser.parse_job_count(listings_raw)
                last_page = math.ceil(total_jobs / self.client.base_params["rows"])
                logger.info(f"Found {total_jobs} jobs")
                logger.info(f"Total pages: {last_page}")

                if page > last_page:
                    logger.info("Everything has already been downloaded.")
                    break
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.output_dir / f"trademe_jobs_page_{region}_{page}_{timestamp}.json"

            with filename.open("w", encoding="utf-8") as f:
                json.dump(listings_raw, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved {filename.name}")
            raw_jobs = listings_raw["List"]
            for job in raw_jobs:
                raw = job
                if raw is None:
                    continue

                raw_category = raw["Category"]
                category_name = self.parser._get_category_name(
                    raw_category,
                    categories,
                )
                raw["CategoryName"] = category_name


                job_details = {
                    "external_reference_id": str(raw["ListingId"]),
                    "source": self.source,
                    "raw": json.dumps(raw),
                    "job_url": raw["CanonicalPath"], 
                    "job_title": raw["Title"] 
                }
                jobs.append(job_details)
                found_new_job += 1
            if found_new_job == 0:
                page_since_last_new_job+=1
            
            if page_since_last_new_job == 2:
                logger.info(f"Stopping trademe collector ... no new jobs found since the last {page_since_last_new_job} page")
                break

            if page == last_page:
                end_filename = filename.with_name(
                    filename.stem + "_END" + filename.suffix
                )
                filename.rename(end_filename)
                logger.info(f"Marked crawl complete: {end_filename.name}")
                break
            page += 1
            requests_since_long_sleep += 1
            self._short_sleep()
            if requests_since_long_sleep >= requests_until_long_sleep:
                self._long_sleep()
                requests_since_long_sleep = 0
                requests_until_long_sleep = random.randint(3, 6)

        return jobs

    def collect(self):
        wellington_jobs = self.collect_region("wellington")
        auckland_jobs = self.collect_region("auckland")
        jobs = wellington_jobs + auckland_jobs
        for job in jobs:
            self.storage.save(job)

class JobsGovtCollector(Collector):
    def __init__(self, 
        client: JobsGovtClient, 
        parser: JobsGovtRawParser, 
        storage: PostgreSQLRawStorage 
    ) -> None:
        self.source = "jobs_govt_nz"
        self.client = client
        self.parser = parser 
        self.storage = storage
        self.total_jobs = 0

    def collect(self):
        page = "0"
        next_page = 1
        jobs = []
        while True:
            found_new_job = False
            logger.info(f"Fetching jobs from page # {next_page}")
            if self.total_jobs and int(page) >= self.total_jobs:
                break
            main_page_html = self.client.get_listing_page(page)
            page = str(next_page*20)
            next_page += 1

            if not self.total_jobs:
                self.total_jobs = self.parser.parse_job_count(main_page_html)

            listings = self.parser.parse_listings(main_page_html)
            for listing in listings:
                listing_page = self.client.get_job_page(listing["job_url"])
                listing_details = self.parser.parse_details(listing_page)
                if listing_details is None:
                    continue
                job = {
                    **listing_details,
                    "source": self.source,
                    "job_url": listing["job_url"],
                    "job_title": listing["job_title_text"]
                }
                if self.storage.save(job):
                    found_new_job = True

            if not found_new_job:
                logger.info("No New jobs found... breaking the cycle")
                break
