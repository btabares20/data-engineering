from sqlalchemy import create_engine
from db.config import POSTGRES_URL
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

engine=create_engine(POSTGRES_URL)
