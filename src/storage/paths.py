import hashlib
import json
import os
from pathlib import Path

from storage.local import LocalStorage
from sources.contracts import source_id


LAYERS = {"raw", "staging", "curated", "rejected"}


def artifact_directory(layer, source, run_id):
    source_id(source)
    if layer not in LAYERS or not run_id:
        raise ValueError("A known layer, source, and nonempty run ID are required")
    run_key = hashlib.sha256(str(run_id).encode()).hexdigest()[:24]
    return Path(os.getenv("PIPELINE_DATA_DIR", "data")) / layer / source / run_key


def staging_file(source, run_id):
    return artifact_directory("staging", source, run_id) / "jobs.jsonl"


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(path, source, run_id, row_count):
    manifest = {"source": source, "run_id": str(run_id), "row_count": row_count, "sha256": checksum(path)}
    LocalStorage().save_json(Path(path).with_suffix(".manifest.json"), manifest)


def verify_manifest(path, source, run_id):
    path = Path(path)
    manifest = json.loads(path.with_suffix(".manifest.json").read_text())
    if manifest.get("source") != source or manifest.get("run_id") != str(run_id):
        raise ValueError("Staging artifact belongs to a different source or run")
    if manifest.get("sha256") != checksum(path):
        raise ValueError("Staging artifact checksum does not match")
    with path.open(encoding="utf-8") as stream:
        row_count = sum(1 for line in stream if line.strip())
    if manifest.get("row_count") != row_count:
        raise ValueError("Staging artifact row count does not match")
    return manifest
