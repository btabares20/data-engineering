import json

from db.engine import db_context
from db.models import Staging, Raw
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from utils.common import pipeline_step

source = "jobs_govt_nz"
step_name = f"loader:{source}"
parsed_file = f"{source}_parsed.json"
parsed_file = Path(__file__).resolve().parents[1] / parsed_file 

@pipeline_step(step_name)
def main(run_id,metrics):
    with db_context() as db:
        with open(parsed_file, 'r') as file:
            for line in file:
                if not line.strip():
                    continue
                
                metrics.rows_in +=1
                try:
                    data = json.loads(line.strip())
                    data.pop("reference", None)
                    stmt = insert(Staging).values(**data)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["raw_id"],
                        set_={
                            **{
                                c.name: stmt.excluded[c.name]
                                for c in Staging.__table__.columns
                                if c.name not in {"id", "raw_id", "created_at", "updated_at"}
                                },
                            "updated_at": func.now(),
                        },
                    )
                    db.execute(stmt)
                    db.query(Raw).filter(
                        Raw.id == data["raw_id"]
                    ).update(
                        {"parsed": True}
                    )
                
                    metrics.rows_out +=1

                except Exception:
                    metrics.rows_failed += 1
                    raise
                db.commit()
