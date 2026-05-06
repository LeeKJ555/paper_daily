from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import load_config
from .enrichment import enrich_papers
from .metadata import MetadataStore, PaperRecord
from .models import Paper, identity_keys, stable_key
from .output import write_index, write_summary
from .pdf import download_pdf, extract_pdf_text, focused_excerpt
from .ranking import dedupe_papers, rank_papers
from .source_cache import SourceCache
from .sources import fetch_arxiv, fetch_dblp, fetch_openalex, fetch_usenix
from .summarizer import summarize_paper


FETCHERS = {
    "arxiv": fetch_arxiv,
    "openalex": fetch_openalex,
    "dblp": fetch_dblp,
    "usenix": fetch_usenix,
}


def run(config_path: str = "config.yaml", dry_run: bool = False) -> int:
    config = load_config(config_path)
    papers = collect_papers(config)
    papers = enrich_papers(papers, config)
    if not dry_run:
        update_source_cache(config, papers)
    summarizable = filter_summarizable_papers(papers, config)
    ranked = rank_papers(dedupe_papers(summarizable), config)
    metadata = MetadataStore(config.get("storage", {}).get("metadata_path", "data/papers.jsonl"))
    max_papers = max_papers_per_run(config)
    selected = [paper for paper in ranked if not metadata.has_seen(paper)][:max_papers]

    if dry_run:
        print(f"Fetched {len(papers)} papers; {len(ranked)} matched; {len(selected)} new selected.")
        for paper in selected:
            safe_print(f"[{paper.score:02d}] {paper.source} | {paper.title}")
        return 0

    api_key_env = config.get("summary", {}).get("api_key_env", "OPENAI_API_KEY")
    if config.get("run", {}).get("require_openai_key", True) and not os.getenv(api_key_env):
        raise RuntimeError(f"{api_key_env} is required. Set it locally or in GitHub Actions secrets.")

    run_date = datetime.now(ZoneInfo(config.get("run", {}).get("timezone", "Asia/Shanghai"))).date().isoformat()
    written: list[tuple[Paper, Path]] = []
    for paper in selected:
        fulltext, pdf_downloaded = _fulltext_for_paper(paper, config)
        summary = summarize_paper(paper, config, fulltext)
        path = write_summary(config.get("storage", {}).get("summaries_dir", "summaries"), run_date, paper, summary)
        metadata.add(
            PaperRecord(
                stable_key=stable_key(paper),
                identity_keys=sorted(identity_keys(paper)),
                paper=paper.to_dict(),
                summary_path=str(path).replace("\\", "/"),
                run_date=run_date,
                pdf_downloaded=pdf_downloaded,
                fulltext_used=bool(fulltext),
            )
        )
        metadata.write()
        written.append((paper, path))
        safe_print(f"Wrote {path}")

    index_path = write_index(config.get("storage", {}).get("summaries_dir", "summaries"), run_date, written)
    metadata.write()
    safe_print(f"Wrote {index_path}")
    safe_print(f"Done. New summaries: {len(written)}")
    return 0


def max_papers_per_run(config: dict) -> int:
    run_config = config.get("run", {})
    return int(run_config.get("max_papers_per_run", run_config.get("max_papers_per_day", 20)))


def safe_print(message: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    print(message.encode(encoding, errors="replace").decode(encoding, errors="replace"))


def collect_papers(config: dict) -> list[Paper]:
    papers: list[Paper] = []
    for name, fetcher in FETCHERS.items():
        try:
            fetched = fetcher(config)
            print(f"{name}: fetched {len(fetched)} papers")
            papers.extend(fetched)
        except Exception as exc:
            print(f"WARNING: source {name} failed: {exc}")
    return papers


def filter_summarizable_papers(papers: list[Paper], config: dict) -> list[Paper]:
    usenix_config = config.get("sources", {}).get("usenix", {})
    include_unpublished = bool(usenix_config.get("include_unpublished", False))
    dblp_config = config.get("sources", {}).get("dblp", {})
    require_dblp_content = bool(dblp_config.get("require_public_content", True))
    filtered: list[Paper] = []
    for paper in papers:
        if (
            paper.source == "usenix"
            and not include_unpublished
            and not paper.pdf_url
            and not paper.abstract
            and not paper.raw.get("has_public_content", False)
        ):
            continue
        if (
            paper.source == "dblp"
            and require_dblp_content
            and not paper.abstract
            and not paper.pdf_url
        ):
            continue
        filtered.append(paper)
    return filtered


def update_source_cache(config: dict, papers: list[Paper]) -> None:
    cache_path = config.get("storage", {}).get("source_cache_path")
    if not cache_path:
        return
    cache = SourceCache(cache_path)
    added = cache.add_many(papers)
    if added:
        cache.write()


def bootstrap_source(config_path: str = "config.yaml", source: str = "usenix") -> int:
    config = load_config(config_path)
    if source != "usenix":
        raise ValueError("Only the usenix source supports bootstrap in v1.1.")
    papers = fetch_usenix(config, mode="bootstrap")
    cache = SourceCache(config.get("storage", {}).get("source_cache_path", "data/source_cache.jsonl"))
    added = cache.add_many(papers)
    cache.write()
    print(f"Bootstrap {source}: fetched {len(papers)} papers, added {added} new records.")
    return 0


def check_sources(config_path: str = "config.yaml") -> int:
    config = load_config(config_path)
    failed = 0
    for name, fetcher in FETCHERS.items():
        try:
            fetched = fetcher(config)
            print(f"OK {name}: {len(fetched)} papers")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    return 1 if failed else 0


def summarize_missing(config_path: str = "config.yaml") -> int:
    # v1 records are append-only. Missing-summary repair is intentionally conservative:
    # rerunning `paper-daily run` will skip already recorded papers, so this command
    # reports state and leaves future repair hooks clear.
    config = load_config(config_path)
    metadata = MetadataStore(config.get("storage", {}).get("metadata_path", "data/papers.jsonl"))
    missing = [
        record
        for record in metadata.records.values()
        if record.summary_path and not Path(record.summary_path).exists()
    ]
    if not missing:
        print("No missing summaries found.")
        return 0
    print("Missing summaries:")
    for record in missing:
        print(f"- {record.stable_key}: {record.summary_path}")
    return 1


def _fulltext_for_paper(paper: Paper, config: dict) -> tuple[str, bool]:
    pdf_config = config.get("pdf", {})
    if not pdf_config.get("download_open_access", True):
        return "", False
    path = download_pdf(
        paper,
        config.get("storage", {}).get("cache_dir", ".paper-daily-cache"),
        int(pdf_config.get("max_pdf_mb", 30)),
    )
    if not path:
        return "", False
    text = extract_pdf_text(path, int(pdf_config.get("extraction_max_chars", 36000)))
    excerpt = focused_excerpt(text, int(pdf_config.get("focused_excerpt_chars", 18000))) if text else ""
    return excerpt, True
