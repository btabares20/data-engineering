import argparse
import json
import sys
from uuid import uuid4

from sources.contracts import digest
from sources.onboarding import SourceOnboarding
from sources.registry import SourceRegistry


def render_review(registry, identifier):
    if not registry.path(identifier, "proposal.json").exists():
        discovery = registry.read(identifier, "discovery.json")
        return "\n".join([f"Source: {identifier}", "No extraction configuration was proposed.",
                          f"Robots status: {discovery.get('robots', {}).get('status')}"]
                         + discovery.get("robots", {}).get("warnings", []) + discovery.get("warnings", []))
    config = registry.read(identifier, "proposal.json")
    lines = [f"Source: {identifier} ({config.get('name')})", f"URL: {config.get('start_url')}",
             f"Proposal hash: {digest(config)}", f"Mode: {config.get('mode')}", "", "Common field mappings:"]
    for field, rule in sorted(config.get("fields", {}).items()):
        lines.append(f"  {field}: {json.dumps(rule, ensure_ascii=False)}")
    for field, rule in sorted(config.get("detail_fields", {}).items()):
        lines.append(f"  {field} (detail page): {json.dumps(rule, ensure_ascii=False)}")
    if registry.path(identifier, "preview.json").exists():
        preview = registry.read(identifier, "preview.json")
        if preview.get("config_hash") != digest(config):
            lines.extend(["", "Preview is stale: the proposal changed. Run preview before accepting."])
            return "\n".join(lines)
        lines.extend(["", f"Preview ready: {preview.get('ready')}", f"Robots status: {preview.get('robots', {}).get('status')}"])
        lines.extend(preview.get("robots", {}).get("warnings", []))
        lines.extend(preview.get("issues", []))
        lines.append(json.dumps(preview.get("samples", []), indent=2, ensure_ascii=False))
    else:
        discovery = registry.read(identifier, "discovery.json")
        lines.extend(["", f"Robots status: {discovery.get('robots', {}).get('status')}"])
        lines.extend(discovery.get("robots", {}).get("warnings", []))
        lines.extend(discovery.get("warnings", []))
        lines.append("Missing required mappings: " + ", ".join(discovery.get("missing_required_fields", [])))
        lines.append("Run preview before accepting this proposal.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect, review, and run configurable job sources")
    parser.add_argument("--registry")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("source_id")
    inspect.add_argument("url")
    inspect.add_argument("--name")
    propose = commands.add_parser("propose")
    propose.add_argument("file")
    for command in ("preview", "review", "disable", "run"):
        commands.add_parser(command).add_argument("source_id")
    accept = commands.add_parser("accept")
    accept.add_argument("source_id")
    accept.add_argument("--hash", required=True)
    accept.add_argument("--reviewer", required=True)
    accept.add_argument("--terms-reviewed", action="store_true")
    commands.add_parser("list")
    args = parser.parse_args(argv)
    registry = SourceRegistry(args.registry)
    onboarding = SourceOnboarding(registry)
    try:
        if args.command == "inspect":
            result = onboarding.inspect(args.source_id, args.url, args.name)
        elif args.command == "propose":
            with open(args.file, encoding="utf-8") as stream:
                result = {"config_hash": registry.propose(json.load(stream))}
        elif args.command == "preview":
            result = onboarding.preview(args.source_id)
        elif args.command == "review":
            print(render_review(registry, args.source_id))
            return 0
        elif args.command == "accept":
            result = onboarding.accept(args.source_id, args.hash, args.reviewer, args.terms_reviewed)
        elif args.command == "disable":
            registry.disable(args.source_id)
            result = {"source_id": args.source_id, "enabled": False}
        elif args.command == "list":
            result = list(registry.active())
        elif args.command == "run":
            from sources.runtime import run_configured_sources
            from db.engine import db_context
            from transformation.transform import transform
            result = run_configured_sources(str(uuid4()), registry, args.source_id)
            if result:
                with db_context() as db:
                    transform(db)
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
