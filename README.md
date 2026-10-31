# Data engineering pipeline

The pipeline collects New Zealand job listings from Jobs.govt.nz and TradeMe, stores raw records in PostgreSQL, parses them into staging records, and transforms them into job postings. Airflow runs the pipeline daily at 09:00 in its configured timezone.

## Setup

Use Docker with Compose, or Python 3.12 or newer with the packages in requirements.txt. Configure POSTGRES_URL for the application database. Airflow uses a separate metadata database configured in docker-compose.yaml.

Create the shared network with `docker network create data-pipeline` and start the application database with `docker compose -f docker/postgres/docker-compose.yaml up -d`. Configure AIRFLOW_UID and FERNET_KEY in your local environment before initializing Airflow.

Run `docker compose up airflow-init`, then initialize the application schema explicitly:

```sh
docker compose run --rm airflow-cli python -m db.initialize
```

Run this command before enabling the DAG or running the standalone pipeline. It creates missing tables without connecting to the database during model imports. It also applies the additive job-description column migration. Other schema changes require their own migrations.

Start Airflow with `docker compose up -d` and enable the pipeline DAG. The DAG directory is airflow/dags.

For a local Python installation, initialize the schema with `PYTHONPATH=src python -m db.initialize` and run the pipeline with `PYTHONPATH=src python src/orchestrator.py`.

TradeMe checkpoints advance after database writes succeed. Legacy checkpoint files are ignored, so the first run after upgrading can fetch previously downloaded pages again. Database uniqueness constraints prevent duplicate raw records.

## Verification

Run `python -m unittest discover -s tests -v`. The tests use isolated functions and mocked clients and database operations. They require python-dateutil and use mocked clients and database operations without network access or a running database.

## Source request limits

Each source client shares a serial request policy within its process. Requests start at least five seconds apart, with jitter, a connect/read timeout of 10/30 seconds, at most two retries, and exponential backoff. Retry-After seconds and HTTP dates are honored; pauses over 120 seconds defer the crawl instead of retrying early. Three failed requests open a five-minute circuit breaker. Airflow allows one active pipeline run. Automatic redirects are disabled so redirects cannot bypass request pacing.

Set JOBS_GOVT_NZ_REQUEST_INTERVAL or TRADE_ME_REQUEST_INTERVAL to a positive number of seconds to adjust pacing according to source limits. Only the read-only Jobs.govt search POST is retried by that client.

Do not run manual crawls alongside the scheduled DAG. The limiter is per process, not distributed across hosts. For multiple crawlers, use a shared rate limiter or Airflow pools per source. Prefer approved APIs, follow source terms and robots rules, use incremental watermarks and conditional requests where supported, cache unchanged detail pages, and schedule occasional reconciliation instead of frequent full backfills.

## Data quality

Run the explicit schema initializer again before using quality checks to create rejected_records. Transform validates required identities, employer and title, string lengths, New Zealand date ordering, HTTP URLs, listing/closing-date ordering, future listing dates, and salary bounds. It normalizes text, source-relative URLs, and date objects before writing curated rows.

Validation failures are stored in rejected_records with the raw record ID, issue codes, and staging payload. Raw and staging data remain available for correction and replay. Reprocessing a corrected row removes its rejection after a successful curated upsert. Source/reference and staging/raw uniqueness remain enforced by database constraints. The transform logs accepted and rejected counts.

## Pipeline data layers

The database separates immutable source payloads (raw), source-shaped parsed values (staging), validated normalized jobs (job_postings, the curated layer), and quality failures with issue codes (rejected_records). Curated records retain source/reference identity, and staging/rejections link back to raw IDs. Existing database uniqueness constraints enforce these boundaries.

Intermediate files live under PIPELINE_DATA_DIR (default data): raw/<source>/<run-key> for TradeMe page checkpoints and staging/<source>/<run-key>/jobs.jsonl for parsed records. A hash of the exact run ID creates a filesystem-safe run key. Airflow passes its run ID to collectors, parsers, and loaders; the standalone runner generates one UUID for the whole run. Retries reuse their run directory. Separate runs cannot overwrite each other's staging files.

Files are written atomically. Each staging file has a manifest containing its source, run ID, row count, and SHA-256 checksum. Loaders verify the manifest and each raw record's source before staging writes. Empty runs have an explicit zero-row manifest. Legacy files in the working directory are no longer loaded. Docker mounts ./data so all workers on this Compose host share artifacts; workers on multiple hosts need shared storage mounted at the same path. Retain raw/rejected records according to your retention policy and remove old run directories after successful runs.

## Job descriptions and skills

Run `PYTHONPATH=src python -m db.initialize` before this version, or `PYTHONPATH=src python -m db.migrations` to upgrade an already initialized database. The migration adds description and skill columns with ALTER TABLE ADD COLUMN IF NOT EXISTS in one transaction. The Docker equivalent is `docker compose run --rm airflow-cli python -m db.initialize`.

Both source parsers store job_description as plain text while retaining section breaks and stripping script/style content. description_kind distinguishes full descriptions, summaries, and missing text. New TradeMe listings fetch their detail Body through the paced request policy; existing listings reuse saved raw data. Jobs.govt skips detail downloads for known listing URLs. Existing full staging descriptions survive offline replay of older summary-only raw records.

Curated jobs include skills_mentioned, skills_required, skills_evidence, and skills_taxonomy_version. The versioned dictionary covers common technology, office, interpersonal, healthcare, and trade skills. Matching uses word boundaries and canonical aliases. Required skills need explicit requirement wording or a recognized requirements heading. Preferred and negated wording do not become required skills. Evidence includes the matched text and classification for review. Mixed or ambiguous wording is treated conservatively. These are rule-based signals, not an exhaustive interpretation of every job requirement; unknown skills are not inferred, and an empty list does not prove that no skills are required. The full text remains available for auditing and future extraction.

To populate existing jobs without calling source servers, pause scheduled crawls and run:

```sh
PYTHONPATH=src python -m enrichment.backfill --source jobs_govt_nz
PYTHONPATH=src python -m enrichment.backfill --source trade_me
```

The backfill reparses stored raw records through isolated staging artifacts, loads them, and re-runs quality checks and skills extraction. Malformed records are quarantined at the parse stage. Raw payloads are preserved. Older TradeMe records may only contain summaries. Opt into paced detail requests for missing full descriptions with `--source trade_me --fetch-missing`; saved full descriptions are reused. Verify the detail endpoint's availability and permissions for your source account before enabling it. No live source integration was exercised in this change.

## Configurable sources

Add sources without new Python collectors using `PYTHONPATH=src python -m sources inspect SOURCE_ID URL`. The onboarding flow discovers candidate elements or structured JobPosting data, recommends a draft mapping, previews records against the common job schema, and requires explicit human acceptance of the exact reviewed configuration hash. A command-line review screen and JSON contract support a future LLM discovery harness.

robots.txt is checked before sampling, acceptance, and collection. Disallowed or unverifiable policies block activation. Reports warn that websites may prohibit scraping through their terms even when robots.txt allows it. Dynamic sources reuse request pacing, raw/staging/curated/rejected layers, quality checks, and skill extraction. See [the source-engine guide](docs/configurable-sources.md) for commands, limitations, approval behavior, and harness integration.
