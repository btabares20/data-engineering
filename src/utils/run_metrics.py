from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


def upsert_pipeline_metadata(db: Session, metadata):
    try:
        metadata = db.merge(metadata)
        db.commit()
        return metadata
    except SQLAlchemyError:
        db.rollback()
        raise


