from abc import ABC, abstractmethod

from bs4 import BeautifulSoup
from base.clients import Client, JobsGovtClient
from base.parsers import JobsGovtParser, Parser
from base.storage import Storage, PostgreSQLRawStorage
from utils.logging import get_logger

logger = get_logger(__name__)

class Collector(ABC):
    @abstractmethod
    def collect(self)->dict:
        ...

class JobsGovtCollector(Collector):
    def __init__(self, 
        client: Client, 
        parser: Parser, 
        storage: Storage
    ) -> None:
        self.source = "jobs_govt_nz"
        self.client = client
        self.parser = parser 
        self.storage = storage
        self.total_jobs = 0
        self.metrics = {}

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

        return self.metrics 
