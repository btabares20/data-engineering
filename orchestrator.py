import asyncio

from collectors.jobs_govt_nz import main as jobs_govt_nz_collector
from collectors.trade_me import main as trade_me_collector 
from db.mappings import PIPELINE, TRIGGER, Status
from db.models import PipelineRuns
from db.engine import db_context
from parsers.jobs_govt_nz import main as jobs_govt_nz_parse
from parsers.trade_me import main as trade_me_parse 
from loaders.jobs_govt_nz_loader import main as jobs_govt_nz_load
from loaders.trade_me_loader import main as trade_me_load
from transform import main as transform
from utils.common import utc_now
from utils.run_metrics import upsert_pipeline_metadata as pipeline_metadata
from utils.logging import get_logger 

logger = get_logger(__name__)

# will be on airflow or kestra soon, not now tho
async def main():
    with db_context() as db:
        started_at = utc_now()
        pipeline_run = PipelineRuns(
                pipeline_name=PIPELINE,
                trigger_type=TRIGGER,
                status=Status.STARTED.value,
                started_at=started_at,
        )
        pipeline_run= pipeline_metadata(db, pipeline_run)
        run_id = pipeline_run.id
        try:
            logger.info("Starting scrapers...")
            await asyncio.gather(
                asyncio.to_thread(jobs_govt_nz_collector, run_id),
                asyncio.to_thread(trade_me_collector, run_id, "wellington")
            )
            await asyncio.gather(
                asyncio.to_thread(trade_me_collector, run_id, "auckland")
            )

            logger.info("Starting parsers...")
            await asyncio.gather(
                asyncio.to_thread(jobs_govt_nz_parse, run_id),
                asyncio.to_thread(trade_me_parse, run_id),
            )

            logger.info("Starting loaders...")
            await asyncio.gather(
                asyncio.to_thread(jobs_govt_nz_load, run_id),
                asyncio.to_thread(trade_me_load, run_id),
            )

            logger.info("Starting data quality check and transform...")
            await asyncio.to_thread(transform, run_id)
            pipeline_run.status = Status.SUCCESS.value
        except Exception as e:
            logger.exception(str(e))
            pipeline_run.status = Status.FAILED.value
            pipeline_run.elapsed_ms = int(
                (utc_now() - started_at).total_seconds() * 1000
            )
        finally:
            finished_at = utc_now()
            pipeline_run.finished_at = finished_at 
            pipeline_run.elapsed_ms = int(
                (finished_at - started_at).total_seconds() * 1000
            )
            pipeline_run = pipeline_metadata(db, pipeline_run)
            logger.info(f"Run finished - run: {run_id}")


if __name__ == "__main__":
    asyncio.run(main())
