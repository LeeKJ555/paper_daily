from __future__ import annotations

import argparse

from .runner import bootstrap_source, check_sources, run, summarize_missing


def main() -> None:
    parser = argparse.ArgumentParser(prog="paper-daily")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Fetch, rank, summarize, and write daily output.")
    run_parser.add_argument("--config", default="config.yaml")

    dry_parser = subparsers.add_parser("dry-run", help="Fetch and rank papers without writing outputs.")
    dry_parser.add_argument("--config", default="config.yaml")

    check_parser = subparsers.add_parser("sources-check", help="Check each configured source.")
    check_parser.add_argument("--config", default="config.yaml")

    missing_parser = subparsers.add_parser("summarize-missing", help="Report recorded papers whose summary files are missing.")
    missing_parser.add_argument("--config", default="config.yaml")

    bootstrap_parser = subparsers.add_parser("bootstrap", help="Build source discovery cache without generating summaries.")
    bootstrap_parser.add_argument("--config", default="config.yaml")
    bootstrap_parser.add_argument("--source", default="usenix", choices=["usenix"])

    args = parser.parse_args()
    command = args.command or "run"
    if command == "run":
        raise SystemExit(run(getattr(args, "config", "config.yaml"), dry_run=False))
    if command == "dry-run":
        raise SystemExit(run(args.config, dry_run=True))
    if command == "sources-check":
        raise SystemExit(check_sources(args.config))
    if command == "summarize-missing":
        raise SystemExit(summarize_missing(args.config))
    if command == "bootstrap":
        raise SystemExit(bootstrap_source(args.config, args.source))
    parser.print_help()
    raise SystemExit(2)
