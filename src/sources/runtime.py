import json

from sources.contracts import digest, validate_config
from sources.engine import ExtractionEngine
from sources.http import SourceFetcher
from sources.registry import SourceRegistry


class ConfiguredParser:
    def parse_raw(self, raw):
        payload = json.loads(raw.raw)
        if payload.get("record_type") != "configured_job_v1" or payload.get("source") != raw.source:
            raise ValueError("Unexpected configurable-source payload")
        data = dict(payload["data"])
        data.pop("external_reference_id", None)
        return data | {"raw_id": str(raw.id)}


def collect_source(accepted, fetcher, storage):
    config = validate_config(accepted["config"])
    if (digest(config) != accepted.get("config_hash") or not accepted.get("enabled")
            or not accepted.get("approval", {}).get("terms_reviewed") or not accepted["approval"].get("actor")):
        raise ValueError("Collection requires the exact accepted configuration")
    robots = fetcher.check_robots()
    if not robots.get("allowed"):
        raise ValueError("Source cannot run: robots.txt disallows crawling or cannot be verified")
    identifier = config["source_id"]
    engine = ExtractionEngine(config, fetcher, known=lambda reference: storage.contains(identifier, reference))
    saved = 0
    for record in engine.crawl():
        data = record["data"]
        payload = record | {"record_type": "configured_job_v1", "source": identifier, "config_hash": accepted["config_hash"]}
        saved += bool(storage.save({
            "external_reference_id": data["external_reference_id"], "source": identifier,
            "raw": json.dumps(payload, ensure_ascii=False), "job_url": data["job_url"],
            "job_title": data.get("job_title") or "",
        }))
    return {"source": identifier, "config_hash": accepted["config_hash"], "saved": saved, "stop_reason": engine.stop_reason}


def run_configured_sources(run_id, registry=None, identifier=None, fetcher_factory=SourceFetcher):
    from db.engine import db_context
    from db.models import Raw
    from staging.parsers import JobsParser
    from storage.local import LocalStorage
    from storage.postgres import PostgreSQLRawStorage
    from transformation.loaders import loader
    from storage.paths import staging_file

    registry = registry or SourceRegistry()
    reports = []
    for accepted in registry.active(identifier):
        config = accepted["config"]
        source = config["source_id"]
        with db_context() as db:
            storage = PostgreSQLRawStorage(db, Raw, ["source", "external_reference_id"])
            reports.append(collect_source(accepted, fetcher_factory(config), storage))
        with db_context() as db:
            JobsParser(ConfiguredParser(), LocalStorage(), source, db).parse(run_id)
        with db_context() as db:
            loader(db, staging_file(source, run_id), source=source, run_id=run_id)
    return reports
