import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, DateTime, func
from db.engine import Base, SessionLocal, engine

class Staging(Base):
    __tablename__ = "staging"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_title = Column(String)
    employer = Column(String)
    location = Column(String)
    position_type = Column(String)
    category = Column(String)
    date_listed = Column(String)
    salary_range = Column(String)
    closing_date = Column(String)
    external_reference_id = Column(String, unique=True, nullable=False)
    attachment = Column(String)
    file_links = Column(String)
    website = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

SessionLocal.configure(bind=engine)
Base.metadata.create_all(bind=engine)
