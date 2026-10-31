import time
from uuid import uuid4

from sources.contracts import digest, origin, source_id, validate_config
from sources.discovery import recommend, seed_config
from sources.engine import ExtractionEngine
from sources.http import SourceFetcher
from transformation.quality import validate_record
from transformation.salary import split_salary_range


class SourceOnboarding:
    def __init__(self, registry, fetcher_factory=SourceFetcher, clock=time.time):
        self.registry = registry
        self.fetcher_factory = fetcher_factory
        self.clock = clock

    def inspect(self, identifier, url, name=None):
        source_id(identifier)
        if identifier in ("trade_me", "jobs_govt_nz"):
            raise ValueError("Built-in source identifiers are reserved")
        seed = seed_config(identifier, url, name)
        site_origin = origin(url)
        fetcher = self.fetcher_factory(seed)
        robots = fetcher.check_robots()
        report = {"source_id": identifier, "origin": site_origin, "checked_at": self.clock(), "robots": robots}
        if robots["allowed"]:
            try:
                report.update(recommend(fetcher.fetch(url), seed))
                self.registry.write(identifier, "proposal.json", report["proposal"])
            except (ValueError, RuntimeError, OSError, RecursionError) as error:
                report["warnings"] = [f"Source analysis failed ({type(error).__name__}). Check endpoint availability and whether the website permits automated access before adding it."]
        else:
            report["warnings"] = ["The website may not allow scraping. No page was fetched and no extraction proposal was activated."]
        self.registry.write(identifier, "discovery.json", report)
        return report

    def preview(self, identifier):
        config = validate_config(self.registry.read(identifier, "proposal.json"))
        if config["source_id"] != identifier:
            raise ValueError("Proposal source ID does not match its registry entry")
        if origin(config["start_url"]) != self.registry.read(identifier, "discovery.json")["origin"]:
            raise ValueError("Inspect the proposed origin before previewing it")
        fetcher = self.fetcher_factory(config)
        robots = fetcher.check_robots()
        report = {"source_id": identifier, "config_hash": digest(config), "checked_at": self.clock(),
                  "robots": robots, "samples": [], "issues": [], "ready": False}
        if robots["allowed"]:
            try:
                engine = ExtractionEngine(config, fetcher)
                for index, record in enumerate(engine.crawl(max_records=3, max_pages=1)):
                    data = record["data"] | {"source": identifier, "raw_id": str(uuid4())}
                    _, issues = validate_record(data, split_salary_range)
                    report["samples"].append({"data": record["data"], "quality_issues": issues})
                    report["issues"].extend(f"sample {index + 1}: {issue}" for issue in issues)
            except (ValueError, RuntimeError, OSError, RecursionError) as error:
                report["issues"].append(str(error))
            if not report["samples"]:
                report["issues"].append("No job records were extracted; refine the proposed schema")
            report["ready"] = bool(report["samples"]) and not report["issues"]
        self.registry.write(identifier, "preview.json", report)
        return report

    def accept(self, identifier, expected_hash, actor, terms_reviewed):
        return self.registry.accept(identifier, expected_hash, actor, terms_reviewed,
                                    lambda config: self.fetcher_factory(config).check_robots())
