from base.clients import JobsGovtClient
from base.collectors import JobsGovtCollector
from base.parsers import JobsGovtRawParser
from base.storage import PostgreSQLRawStorage
from db.engine import db_context
from db.models import RawV2



def main():
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

    with db_context() as db:
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
                save_model=RawV2
            )
        )
        collector.collect()

if __name__ == "__main__":
    main()
