import argparse
from uuid import uuid4

from sqlalchemy import or_, select
from collection.composer import trade_me_collector
from db.engine import db_context
from db.models import Raw, Staging
from enrichment.descriptions import description_text
from orchestrator import run_jobs_govt_parser, run_jobs_govt_loader, run_trade_me_parser, run_trade_me_loader, run_transform


def backfill_source(source, fetch_missing=False):
    runners = {
        "jobs_govt_nz": (run_jobs_govt_parser, run_jobs_govt_loader),
        "trade_me": (run_trade_me_parser, run_trade_me_loader),
    }
    if source not in runners or (fetch_missing and source != "trade_me"):
        raise ValueError("Select a known source; detail fetching is only supported for TradeMe")
    run_id = "description-backfill-" + str(uuid4())
    with db_context() as db:
        db.query(Raw).filter(Raw.source == source).update({"parsed": False}, synchronize_session=False)
        db.commit()
    parser, loader = runners[source]
    parser(run_id)
    loader(run_id)
    if fetch_missing:
        with db_context() as db:
            client = trade_me_collector(db, run_id).client
            query = select(Staging, Raw.external_reference_id).join(Raw).where(
                Raw.source == source,
                or_(Staging.description_kind != "full", Staging.description_kind.is_(None)),
            )
            for staging, reference in db.execute(query).all():
                text = description_text(client.get_job_details(reference).get("Body"))
                if text:
                    staging.job_description = text
                    staging.description_kind = "full"
                    db.commit()
    run_transform()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("jobs_govt_nz", "trade_me"), required=True)
    parser.add_argument("--fetch-missing", action="store_true")
    options = parser.parse_args()
    backfill_source(options.source, options.fetch_missing)


if __name__ == "__main__":
    main()
