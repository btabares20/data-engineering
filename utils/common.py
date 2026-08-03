from datetime import datetime, UTC
from threading import Event
from db.engine import db_context
from db.mappings import Status
from db.models import PipelineSteps
from db.types import StepMetrics
from utils.run_metrics import upsert_pipeline_metadata as pipeline_metadata

def utc_now() -> datetime:
    return datetime.now(UTC)

cancel_event = Event()


def pipeline_step(step_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            run_id = kwargs.get("run_id") or args[0]
            started_at = utc_now()
            metrics = StepMetrics()

            with db_context() as db:
                step = PipelineSteps(
                    pipeline_run_id=run_id,
                    step_name=step_name,
                    status=Status.STARTED.value,
                    started_at=utc_now(),
                )

                step = pipeline_metadata(db, step)

            try:
                result = func(*args, metrics, **kwargs)
                step.status = Status.SUCCESS.value
                return result

            except Exception as e:
                step.status = Status.FAILED.value
                step.error_message = str(e)
                step.elapsed_ms = int(
                    (utc_now()- started_at).total_seconds() * 1000
                )
                raise

            finally:
                finished_at = utc_now()
                step.finished_at = utc_now() 
                step.elapsed_ms = int(
                    (finished_at - started_at).total_seconds() * 1000
                )
                step.rows_in = metrics.rows_in
                step.rows_out = metrics.rows_out
                step.rows_failed = metrics.rows_failed
                step.rows_skipped = metrics.rows_skipped

                with db_context() as db:
                    pipeline_metadata(db, step)

        return wrapper
    return decorator

def pipeline_step_v2(step_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            run_id = kwargs.get("run_id")
            run_id = "3826272f-6f53-4dd0-a612-77809f3ef886"
            started_at = utc_now()
            metrics = StepMetrics()

            with db_context() as db:
                step = PipelineSteps(
                    pipeline_run_id=run_id,
                    step_name=step_name,
                    status=Status.STARTED.value,
                    started_at=utc_now(),
                )

                metrics = pipeline_metadata(db, step)

                try:
                    metrics_result = func(*args , **kwargs)
                    step.status = Status.SUCCESS.value
                    return metrics_result 

                except Exception as e:
                    step.status = Status.FAILED.value
                    step.error_message = str(e)
                    step.elapsed_ms = int(
                        (utc_now()- started_at).total_seconds() * 1000
                    )
                    raise

                finally:
                    finished_at = utc_now()
                    step.finished_at = utc_now() 
                    step.elapsed_ms = int(
                        (finished_at - started_at).total_seconds() * 1000
                    )
                    step.rows_in = metrics.rows_in
                    step.rows_out = metrics.rows_out
                    step.rows_failed = metrics.rows_failed
                    step.rows_skipped = metrics.rows_skipped

                    pipeline_metadata(db, step)

        return wrapper
    return decorator
