from db.engine import Base, engine
from db import models


def initialize():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    initialize()
