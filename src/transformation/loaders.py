import json
from sqlalchemy.orm import Session
from db.engine import db_context
from db.models import Staging, Raw
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from utils.logging import get_logger 
from storage.paths import verify_manifest

logger = get_logger(__name__)

def loader(db: Session, filename: str, *, source: str, run_id: str):
    verify_manifest(filename, source, run_id)
    with open(filename, 'r', encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            try:
                data = json.loads(line.strip())
                logger.debug(data)
                data.pop("reference", None)
                db.query(Raw).filter(Raw.id == data["raw_id"], Raw.source == source).one()
                allowed = {column.name for column in Staging.__table__.columns} - {"id", "created_at", "updated_at"}
                data = {key: value for key, value in data.items() if key in allowed}
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
            except Exception:
                raise
            db.commit()
