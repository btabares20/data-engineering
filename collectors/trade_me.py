import json
import math
import random
import re
import time
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert
from db.engine import db_context
from db.models import Raw
from utils.common import pipeline_step

import requests

URL = "https://api.trademe.co.nz/v1/search/jobs.json"
SOURCE_NAME = "trade_me"
step_name = f"scraper:{SOURCE_NAME}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.trademe.co.nz/",
    "Origin": "https://www.trademe.co.nz",
    "x-trademe-uniqueclientid": "2c72ffa4-eb63-40cf-8f1c-294ffbac6e6a",
    "DNT": "1",
    "Sec-GPC": "1",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

BASE_PARAMS = {
    "rows": 22,
    "return_canonical": "true",
    "return_metadata": "true",
    "return_ads": "true",
    "return_empty_categories": "true",
    "return_super_features": "true",
    "return_did_you_mean": "true",
    "canonical_path": "/jobs/auckland",
    "snap_parameters": "true",
    "photo_size": 6,
    "return_seo_details": "true",
}

OUTPUT_DIR = Path(f"raw_data/{SOURCE_NAME}")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def get_category_name(raw_category: str, categories: dict)-> str | None:
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

def get_resume_page(region) -> int:
    today = datetime.now().strftime("%Y%m%d")

    # Already finished today?
    end_files = sorted(
        OUTPUT_DIR.glob(f"trademe_jobs_page_{region}_*_{today}_*_END.json")
    )

    if end_files:
        raise RuntimeError(
            f"Today's crawl has already completed ({end_files[-1].name})."
        )

    pattern = re.compile(
        rf"trademe_jobs_page_{region}_(\d+)_{today}_\d{{6}}\.json"
    )

    latest_page = 0

    for file in OUTPUT_DIR.glob(f"trademe_jobs_page_{region}_*.json"):
        match = pattern.match(file.name)
        if match:
            latest_page = max(latest_page, int(match.group(1)))

    return latest_page + 1


def short_sleep():
    seconds = random.uniform(2.5, 6.5)
    print(f"Sleeping {seconds:.1f}s...")
    time.sleep(seconds)


def long_sleep():
    seconds = random.uniform(60, 120)
    print(f"Long break for {seconds:.0f}s...")
    time.sleep(seconds)

@pipeline_step(step_name)
def main(run_id, region, metrics):
    HEADERS["canonical_path"]= f"/jobs/{region}"
    print("starting trade_me scraper")
    try:
        page = get_resume_page(region)
    except RuntimeError as e:
        print(str(e))
        return
    print(f"Starting from page {page}")

    session = requests.Session()
    session.headers.update(HEADERS)

    requests_until_long_sleep = random.randint(3, 6)
    requests_since_long_sleep = 0

    total_jobs = None
    last_page = None
    
    with db_context() as db:
        page_since_last_new_job = 0
        while last_page is None or page <= last_page:
            found_new_job = 0
            print(f"Fetching page {page}...")

            params = BASE_PARAMS | {
                "page": page,
                "rsqid": "f284381cd41a4b8c92dad9f7464e15d3-001",
            }

            response = session.get(URL, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if total_jobs is None:
                total_jobs = data["TotalCount"]  # Change if necessary
                last_page = math.ceil(total_jobs / BASE_PARAMS["rows"])

                print(f"Found {total_jobs} jobs")
                print(f"Total pages: {last_page}")

                if page > last_page:
                    print("Everything has already been downloaded.")
                    return

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = OUTPUT_DIR / f"trademe_jobs_page_{region}_{page}_{timestamp}.json"

            with filename.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"Saved {filename.name}")
            jobs = data["List"]
            for job in jobs:
                metrics.rows_in += 1
                raw = job 
                try:
                    raw_category = raw.get("Category")
                    category_name = get_category_name(raw_category, data["FoundCategories"])
                    raw["CategoryName"]= category_name
                    external_reference_id = str(raw["ListingId"])
                    title = raw["Title"]
                    job_url = raw["CanonicalPath"]
                    exists = db.query(Raw).filter(
                        Raw.source == SOURCE_NAME,
                        Raw.external_reference_id == external_reference_id
                    ).first()

                    if exists:
                        print(f"Already exists: {external_reference_id}")
                        metrics.rows_skipped += 1
                        continue
                    else:
                        found_new_job += 1
                        print(f"Job not yet on db: {external_reference_id}")

                    raw_data = {
                        "external_reference_id": external_reference_id,
                        "source": SOURCE_NAME,
                        "raw": json.dumps(raw),
                        "job_url": job_url, 
                        "job_title": title
                    }

                    stmt = insert(Raw).values(**raw_data)

                    stmt = stmt.on_conflict_do_nothing(
                        index_elements=[
                            "source",
                            "external_reference_id",
                        ]
                    )

                    db.execute(stmt)
                    print(
                        f"Saved job {title} #{external_reference_id} in raw"
                    )
                    metrics.rows_out += 1
                except Exception as e:
                    metrics.rows_failed += 1
                    print(f"Failed {job.get('ListingId')}: {e}")
                    continue

            db.commit()
            if found_new_job == 0:
                page_since_last_new_job+=1
            
            if page_since_last_new_job == 2:
                print(f"Stopping trademe collector ... no new jobs found since the last {page_since_last_new_job} page")
                break

            if page == last_page:
                end_filename = filename.with_name(
                    filename.stem + "_END" + filename.suffix
                )
                filename.rename(end_filename)
                print(f"Marked crawl complete: {end_filename.name}")
                break

            page += 1
            requests_since_long_sleep += 1

            short_sleep()

            if requests_since_long_sleep >= requests_until_long_sleep:
                long_sleep()
                requests_since_long_sleep = 0
                requests_until_long_sleep = random.randint(3, 6)

        print("Done.")
