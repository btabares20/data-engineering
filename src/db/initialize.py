from db.engine import Base, engine
from db import models
from db.migrations import upgrade_job_descriptions


def initialize():
    Base.metadata.create_all(bind=engine)
    upgrade_job_descriptions()


if __name__ == "__main__":
    initialize()
