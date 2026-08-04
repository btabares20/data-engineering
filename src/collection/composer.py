from collection.base import Collector
from collection.clients import JobsGovtClient, TradeMeClient
from collection.collectors import JobsGovtCollector, TradeMeCollector
from collection.parsers import JobsGovtRawParser, TradeMeRawParser
from storage.postgres import PostgreSQLRawStorage
from db.engine import db_context
from db.models import Raw

from sqlalchemy.orm import Session


def jobs_govt_collector(db: Session)->Collector:
    base_url = "https://jobs.govt.nz"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    body = {
        "in_version": "",
        "in_sessionid": "",
        "in_graphic": "",
        "javaProxyUrl": "",
        "in_param": "",
        "in_organid": "16563",
        "in_others": "",
        "in_orderby": "dateinput desc",
        "in_skills": "",
        "in_location": "",
        "in_multi01": "",
        "in_multi01_id": "1802",
        "in_searchBut": "",
        "in_pg": "0",
    }

    collector = JobsGovtCollector(
        client = JobsGovtClient(
            base_url=base_url,
            headers=headers,
            body=body
        ),
        parser = JobsGovtRawParser(),
        storage = PostgreSQLRawStorage(
            session=db,
            conflict_columns=[
                "source",
                "external_reference_id"
            ],
            save_model=Raw
        )
    )
    return collector 


def trade_me_collector(db: Session)->Collector:
    url = "https://api.trademe.co.nz/v1/search/jobs.json"
    source = "trade_me"
    headers = {
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

    base_params = {
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
    collector = TradeMeCollector(
        client = TradeMeClient(
            url=url,
            headers=headers,
            params=base_params
        ),
        parser = TradeMeRawParser(),
        storage = PostgreSQLRawStorage(
            session=db,
            conflict_columns=[
                "source",
                "external_reference_id"
            ],
            save_model=Raw
        )
    )
    return collector
