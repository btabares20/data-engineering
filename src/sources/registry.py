import json
import os
from pathlib import Path
import time

from sources.contracts import digest, source_id, validate_config
from storage.local import LocalStorage


class SourceRegistry:
    def __init__(self, root=None, clock=time.time):
        self.root = Path(root or os.getenv("SOURCE_REGISTRY_DIR", str(Path(os.getenv("PIPELINE_DATA_DIR", "data")) / "sources")))
        self.clock = clock
        self.storage = LocalStorage()

    def path(self, identifier, filename):
        return self.root / source_id(identifier) / filename

    def write(self, identifier, filename, data):
        self.storage.save_json(self.path(identifier, filename), data)

    def read(self, identifier, filename):
        return json.loads(self.path(identifier, filename).read_text(encoding="utf-8"))

    def propose(self, config):
        validate_config(config)
        analysis = self.read(config["source_id"], "discovery.json")
        from sources.contracts import origin
        if origin(config["start_url"]) != analysis["origin"]:
            raise ValueError("A proposal must stay on its inspected origin")
        self.write(config["source_id"], "proposal.json", config)
        return digest(config)

    def accept(self, identifier, expected_hash, actor, terms_reviewed, robots_check):
        config = validate_config(self.read(identifier, "proposal.json"))
        from sources.contracts import origin
        if origin(config["start_url"]) != self.read(identifier, "discovery.json")["origin"]:
            raise ValueError("Inspect the proposed origin before accepting it")
        fingerprint = digest(config)
        preview = self.read(identifier, "preview.json")
        if config["source_id"] != identifier or fingerprint != expected_hash or preview.get("config_hash") != fingerprint:
            raise ValueError("Proposal changed; preview and review its current hash again")
        if not isinstance(actor, str) or not actor.strip() or not terms_reviewed:
            raise ValueError("Identify the reviewer and acknowledge reviewing source terms and permission")
        if not preview.get("ready") or not 0 <= self.clock() - preview.get("checked_at", 0) <= 86400:
            raise ValueError("A successful preview from the last 24 hours is required")
        robots = robots_check(config)
        if not robots.get("allowed"):
            raise ValueError("robots.txt disallows crawling or cannot be verified; source is not activated")
        accepted = {"config": config, "config_hash": fingerprint, "enabled": True,
                    "approval": {"actor": actor.strip(), "terms_reviewed": True, "accepted_at": self.clock(), "robots": robots}}
        self.write(identifier, f"history/{fingerprint}.json", accepted)
        self.write(identifier, "accepted.json", accepted)
        return accepted

    def active(self, identifier=None):
        paths = [self.path(identifier, "accepted.json")] if identifier else sorted(self.root.glob("*/accepted.json"))
        for path in paths:
            accepted = json.loads(path.read_text(encoding="utf-8"))
            config = validate_config(accepted["config"])
            if source_id(path.parent.name) != config["source_id"] or digest(config) != accepted.get("config_hash"):
                raise ValueError("Accepted configuration was modified; review it again")
            if not accepted.get("approval", {}).get("terms_reviewed") or not accepted["approval"].get("actor"):
                raise ValueError("Source lacks an explicit review record")
            if accepted.get("enabled"):
                yield accepted

    def disable(self, identifier):
        accepted = self.read(identifier, "accepted.json")
        accepted["enabled"] = False
        self.write(identifier, "accepted.json", accepted)
