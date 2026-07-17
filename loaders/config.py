import os

POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://postgres:password@localhost:5432/postgres"
)
