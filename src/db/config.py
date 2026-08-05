import os

POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://postgres:password@postgres_db:5432/postgres"
)
