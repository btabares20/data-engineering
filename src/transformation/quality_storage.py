import json
from sqlalchemy.dialects.postgresql import insert
from db.models import RejectedRecord


def record_rejection(db, data, issues, stage="transform"):
    payload = json.loads(json.dumps(data, default=str))
    statement = insert(RejectedRecord).values(
        raw_id=data["raw_id"], stage=stage, issues=issues, payload=payload,
    )
    db.execute(statement.on_conflict_do_update(
        index_elements=["raw_id", "stage"],
        set_={"issues": statement.excluded.issues, "payload": statement.excluded.payload},
    ))


def clear_rejection(db, raw_id, stage="transform"):
    db.query(RejectedRecord).filter(
        RejectedRecord.raw_id == raw_id, RejectedRecord.stage == stage,
    ).delete(synchronize_session=False)
