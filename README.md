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

## Source request limits

Each source client shares a serial request policy within its process. Requests start at least five seconds apart, with jitter, a connect/read timeout of 10/30 seconds, at most two retries, and exponential backoff. Retry-After seconds and HTTP dates are honored; pauses over 120 seconds defer the crawl instead of retrying early. Three failed requests open a five-minute circuit breaker. Airflow allows one active pipeline run. Automatic redirects are disabled so redirects cannot bypass request pacing.

Set JOBS_GOVT_NZ_REQUEST_INTERVAL or TRADE_ME_REQUEST_INTERVAL to a positive number of seconds to adjust pacing according to source limits. Only the read-only Jobs.govt search POST is retried by that client.

Do not run manual crawls alongside the scheduled DAG. The limiter is per process, not distributed across hosts. For multiple crawlers, use a shared rate limiter or Airflow pools per source. Prefer approved APIs, follow source terms and robots rules, use incremental watermarks and conditional requests where supported, cache unchanged detail pages, and schedule occasional reconciliation instead of frequent full backfills.

## Data quality

Run the explicit schema initializer again before using quality checks to create rejected_records. Transform validates required identities, employer and title, string lengths, New Zealand date ordering, HTTP URLs, listing/closing-date ordering, future listing dates, and salary bounds. It normalizes text, source-relative URLs, and date objects before writing curated rows.

Validation failures are stored in rejected_records with the raw record ID, issue codes, and staging payload. Raw and staging data remain available for correction and replay. Reprocessing a corrected row removes its rejection after a successful curated upsert. Source/reference and staging/raw uniqueness remain enforced by database constraints. The transform logs accepted and rejected counts.
