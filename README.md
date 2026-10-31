# Data engineering pipeline

The pipeline collects New Zealand job listings from Jobs.govt.nz and TradeMe, stores raw records in PostgreSQL, parses them into staging records, and transforms them into job postings. Airflow runs the pipeline daily at 09:00 in its configured timezone.

## Setup

Use Docker with Compose, or Python 3.12 or newer with the packages in requirements.txt. Configure POSTGRES_URL for the application database. Airflow uses a separate metadata database configured in docker-compose.yaml.

Create the shared network with `docker network create data-pipeline` and start the application database with `docker compose -f docker/postgres/docker-compose.yaml up -d`. Configure AIRFLOW_UID and FERNET_KEY in your local environment before initializing Airflow.

Run `docker compose up airflow-init`, then initialize the application schema explicitly:

```sh
docker compose run --rm airflow-cli python -m db.initialize
```

Run this command before enabling the DAG or running the standalone pipeline. It creates missing tables without connecting to the database during model imports. It does not migrate existing table definitions.

Start Airflow with `docker compose up -d` and enable the pipeline DAG. The DAG directory is airflow/dags.

For a local Python installation, initialize the schema with `PYTHONPATH=src python -m db.initialize` and run the pipeline with `PYTHONPATH=src python src/orchestrator.py`.

TradeMe checkpoints advance after database writes succeed. Legacy checkpoint files are ignored, so the first run after upgrading can fetch previously downloaded pages again. Database uniqueness constraints prevent duplicate raw records.

## Verification

Run `python -m unittest discover -s tests -v`. The tests use isolated functions and mocked clients and database operations. They do not require application dependencies, network access, or a running database.
