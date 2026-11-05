import asyncio
from uuid import uuid4
from storage.paths import staging_file
from collection.composer import jobs_govt_collector, trade_me_collector
from db.engine import db_context
from staging.composer import jobs_govt_nz_parser, trade_me_parser
from transformation.loaders import loader
from transformation.transform import transform
from utils.logging import get_logger 

logger = get_logger(__name__)

def run_jobs_govt_collector(run_id):
    with db_context() as db:
        jobs_govt_collector(db).collect()

def run_trade_me_collector(run_id):
    with db_context() as db:
        trade_me_collector(db, run_id).collect()

def run_jobs_govt_parser(run_id):
    with db_context() as db:
        jobs_govt_nz_parser(db).parse(run_id)

def run_trade_me_parser(run_id):
    with db_context() as db:
        trade_me_parser(db).parse(run_id)

def run_jobs_govt_loader(run_id):
    with db_context() as db:
        loader(db, staging_file("jobs_govt_nz", run_id), source="jobs_govt_nz", run_id=run_id)

def run_trade_me_loader(run_id):
    with db_context() as db:
        loader(db, staging_file("trade_me", run_id), source="trade_me", run_id=run_id)

def run_transform():
    with db_context() as db:
        transform(db)


async def main():
    run_id = str(uuid4())
    with db_context() as db:
        try:
            logger.info("Starting collectors...")
            await asyncio.gather(
                asyncio.to_thread(run_jobs_govt_collector, run_id),
                asyncio.to_thread(run_trade_me_collector, run_id)
            )
            logger.info("Starting parsers...")
            await asyncio.gather(
                asyncio.to_thread(run_jobs_govt_parser, run_id),
                asyncio.to_thread(run_trade_me_parser, run_id)
            )
            logger.info("Starting loaders...")
            await asyncio.gather(
                asyncio.to_thread(run_jobs_govt_loader, run_id),
                asyncio.to_thread(run_trade_me_loader, run_id)
            )
            logger.info("Starting data quality check and transform...")
            await asyncio.to_thread(run_transform)
        except Exception as e:
            logger.exception(str(e))
            raise

    logger.info("Pipeline finished...")

if __name__ == "__main__":
    asyncio.run(main())
