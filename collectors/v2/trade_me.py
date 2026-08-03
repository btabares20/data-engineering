from base.clients import TradeMeClient
from base.collectors import TradeMeCollector
from base.parsers import TradeMeRawParser
from base.storage import PostgreSQLRawStorage
from db.engine import db_context
from db.models import Raw 

def main():
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

    with db_context() as db:
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
        collector.collect()

if __name__ == "__main__":
    main()
