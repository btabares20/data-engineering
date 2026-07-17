import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Boolean, Column, ForeignKey, String, DateTime, UniqueConstraint, func
from sqlalchemy.orm import relationship
from db.engine import Base, SessionLocal, engine

class Staging(Base):
    __tablename__ = "staging"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_id = Column(UUID(as_uuid=True), ForeignKey("raw.id"), nullable=False)
    job_title = Column(String)
    employer = Column(String)
    location = Column(String)
    position_type = Column(String)
    category = Column(String)
    date_listed = Column(String)
    salary_range = Column(String)
    closing_date = Column(String)
    attachment = Column(String)
    file_links = Column(String)
    website = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    raw = relationship("Raw", back_populates="staging")
    __table_args__ = (
        UniqueConstraint(
            "raw_id",
            name="uq_staging_raw_id",
        ),
    )

class Raw(Base):
    __tablename__ = "raw"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_reference_id = Column(String, nullable=False)
    parsed = Column(Boolean, default=False)
    raw_html = Column(String, nullable=False)
    source = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    staging = relationship("Staging", back_populates="raw")
    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_reference_id",
            name="uq_raw_source_external_ref",
        ),
    )

SessionLocal.configure(bind=engine)
Base.metadata.create_all(bind=engine)
