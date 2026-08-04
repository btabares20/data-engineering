import os
import json

from sqlalchemy.dialects.postgresql import insert

from db.engine import db_context
from db.models import Raw

SOURCE_NAME = "trade_me"
DATA_DIR = f"./raw_data/{SOURCE_NAME}"
files_list = os.listdir(DATA_DIR)

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

with db_context() as db:
    print("Loading trade_me into raw retroactively")
    for file in files_list:
        with open(os.path.join(DATA_DIR, file),'r') as f:
            data = json.loads(f.read())
        jobs = data["List"]
        for job in jobs:
            raw = job 
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
                continue
            else:
                found_new_job = True
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
        db.commit()

