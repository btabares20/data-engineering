from abc import ABC, abstractmethod
from typing import Any
from bs4 import BeautifulSoup, Tag 
from utils.logging import get_logger

logger = get_logger(__name__)


class JobsGovtRawParser:
    def parse_job_count(self, data: str) -> int:
        parser = BeautifulSoup(data, "html.parser")
        tag = parser.find("input", attrs={"name": "in_totalrows"})
        
        if not isinstance(tag, Tag):
            logger.warning("Could not find tag for total jobs input")
            return 0

        value = tag.get("value")
        if value is None:
            logger.warning("Expected 'value' attribute.")
            return 0        

        if isinstance(value, list):
            logger.warning("Expected scalar value, got list: %r", value)
            return 0

        try:
            total_jobs = int(value)
        except (TypeError, ValueError):
            logger.warning("Invalid total jobs value: %r", value)
            return 0

        logger.info("Found %d jobs", total_jobs)
        return total_jobs

    def _parse_job_metadata(self, row: Tag) -> dict | None:
        if row is not None:
            title_td = row.find("td", class_="job_title")
            if not title_td:
                logger.warning("Skipping row")
                return None
            
            first_link = title_td.find("a")
            first_div = title_td.find("div")

            job_title = first_link.text.strip() if first_link else None
            job_url = first_link["href"] if first_link else None

            if first_div is None:
                logger.warning("Could not find div for job title")
                company = None
            else:
                company = first_div.text.replace("at","").strip()

            job_meta_data = {
                "job_title_text" : job_title,
                "job_url" : job_url,
                "company": company 
            }

            return job_meta_data
        return None

    def _parse_job_reference_id(self, details_parser: BeautifulSoup) -> str | None:
        details_table = details_parser.select_one("div[class^='job-details']")
        if not details_table:
            return None

        for row in details_table.find_all('tr'):
            cells = row.find_all("td")

            if len(cells) < 2:
                return None

            if "Reference" in cells[0].get_text(strip=True):
                return cells[1].get_text(strip=True)

        return None

    def parse_listings(self, data: str) -> list[dict]:
        listings = []
        listing_parser = BeautifulSoup(data, "html.parser")
        for tr in listing_parser.find_all("tr"):
            listing = self._parse_job_metadata(tr)
            if listing:
                listings.append(listing)
        return listings

    def parse_details(self, data: str) -> dict | None:
        details_parser = BeautifulSoup(data, "html.parser")
        job_reference_id = self._parse_job_reference_id(details_parser)
        if not job_reference_id:
            logger.warning(f"Skipping job without reference")
            return None

        job_raw_data = {
            "external_reference_id": job_reference_id,
            "raw": details_parser.prettify()
        }
        return job_raw_data

class TradeMeRawParser:
    # kind shitty because we don't need to parse trademe
    def parse_job_count(self, data: dict)->int:
        if "TotalCount" not in data:
            logger.warning("Could not determine proper job count")
            return 0
        return data["TotalCount"]

    def _get_category_name(self, raw_category: str, categories: dict)-> str | None:
        category_split = raw_category.rstrip("-").split("-")
        category_code_prefix = "-".join(category_split[:2]) + "-"
        category_code_name = int(category_split[1])
        category_name = next(
            (
                category["Name"] for category in categories 
                if category.get("Category") == category_code_prefix 
                and category.get("CategoryId") == category_code_name
            ),
            None,
        )
        return category_name
    
    def _get_categories(self, data: dict) -> dict:
        return data["FoundCategories"]

    def parse_listings(self, data: dict)->list[dict]:
        return data["List"]

