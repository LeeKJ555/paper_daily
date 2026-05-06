from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from paper_daily.metadata import MetadataStore, PaperRecord
from paper_daily.models import Paper, identity_keys, stable_key
from paper_daily.output import summary_filename
from paper_daily.ranking import dedupe_papers, rank_papers
from paper_daily.source_cache import SourceCache


def test_stable_key_prefers_doi() -> None:
    paper = Paper(paper_id="x", title="A Kernel Paper", doi="https://doi.org/10.1/ABC")
    assert stable_key(paper) == "doi:10.1/abc"


def test_dedupe_by_normalized_title_when_no_doi() -> None:
    papers = [
        Paper(paper_id="a", title="CXL Memory Tiering!"),
        Paper(paper_id="b", title="CXL memory tiering"),
    ]
    assert len(dedupe_papers(papers)) == 1


def test_rank_papers_scores_topic_pdf_and_recent() -> None:
    config = {
        "run": {"lookback_days": 14},
        "ranking": {
            "minimum_score": 1,
            "title_weight": 4,
            "abstract_weight": 1,
            "venue_weight": 3,
            "pdf_weight": 2,
            "recent_weight": 2,
        },
        "topics": [{"name": "tiered-memory", "keywords": ["CXL", "tiered memory"]}],
        "sources": {"dblp": {"venues": ["OSDI"]}},
    }
    paper = Paper(
        paper_id="p",
        title="CXL Tiered Memory for Kernels",
        abstract="memory tiering",
        venue="OSDI",
        pdf_url="https://arxiv.org/pdf/1.pdf",
        published_at=datetime.now(timezone.utc),
    )
    ranked = rank_papers([paper], config)
    assert ranked[0].score >= 12
    assert ranked[0].topics == ["tiered-memory"]


def test_arxiv_requires_strong_keyword_when_configured() -> None:
    config = {
        "run": {"lookback_days": 14},
        "ranking": {
            "minimum_score": 1,
            "arxiv_minimum_score": 5,
            "title_weight": 4,
            "pdf_weight": 2,
            "recent_weight": 2,
            "arxiv_required_keywords": ["kernel", "tiered memory"],
        },
        "topics": [{"name": "systems", "keywords": ["system"]}],
        "sources": {"dblp": {"venues": []}},
    }
    broad = Paper(
        paper_id="arxiv:1",
        title="Authentication System",
        source="arxiv",
        pdf_url="https://arxiv.org/pdf/1",
        published_at=datetime.now(timezone.utc),
    )
    strong = Paper(
        paper_id="arxiv:2",
        title="Kernel System",
        source="arxiv",
        pdf_url="https://arxiv.org/pdf/2",
        published_at=datetime.now(timezone.utc),
    )
    assert [paper.title for paper in rank_papers([broad, strong], config)] == ["Kernel System"]


def test_negative_keywords_reduce_rank() -> None:
    config = {
        "run": {"lookback_days": 14},
        "ranking": {
            "minimum_score": 5,
            "title_weight": 4,
            "pdf_weight": 2,
            "recent_weight": 2,
            "negative_keyword_weight": 5,
            "negative_keywords": ["authentication"],
        },
        "topics": [{"name": "systems", "keywords": ["system"]}],
        "sources": {"dblp": {"venues": []}},
    }
    paper = Paper(
        paper_id="p",
        title="Authentication System",
        pdf_url="https://example.com/p.pdf",
        published_at=datetime.now(timezone.utc),
    )
    assert rank_papers([paper], config) == []


def test_metadata_jsonl_roundtrip(tmp_path) -> None:
    store = MetadataStore(tmp_path / "papers.jsonl")
    paper = Paper(paper_id="arxiv:1", title="Kernel Scheduling")
    store.add(PaperRecord(stable_key(paper), sorted(identity_keys(paper)), paper.to_dict(), "summaries/x.md", "2026-05-06"))
    store.write()
    loaded = MetadataStore(tmp_path / "papers.jsonl")
    assert loaded.has_seen(paper)


def test_metadata_persists_title_alias_for_cross_source_dedupe(tmp_path) -> None:
    store = MetadataStore(tmp_path / "papers.jsonl")
    arxiv_paper = Paper(paper_id="arxiv:1", title="Kernel Scheduling")
    store.add(
        PaperRecord(
            stable_key(arxiv_paper),
            sorted(identity_keys(arxiv_paper)),
            arxiv_paper.to_dict(),
            "summaries/x.md",
            "2026-05-06",
        )
    )
    store.write()

    loaded = MetadataStore(tmp_path / "papers.jsonl")
    openalex_paper = Paper(paper_id="openalex:1", title="Kernel scheduling")
    assert loaded.has_seen(openalex_paper)
    assert len((tmp_path / "papers.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_summary_filename_is_markdown() -> None:
    paper = Paper(paper_id="arxiv:1", title="Kernel Scheduling: A Study")
    assert summary_filename(paper).endswith(".md")


def test_source_cache_refreshes_when_public_content_appears() -> None:
    path = Path("tmp-source-cache-test.jsonl")
    path.unlink(missing_ok=True)
    try:
        cache = SourceCache(path)
        title_only = Paper(paper_id="dblp:1", title="Kernel Scheduling", source="dblp")
        enriched = Paper(
            paper_id="dblp:1",
            title="Kernel Scheduling",
            source="dblp",
            abstract="kernel scheduling",
            pdf_url="https://example.com/p.pdf",
        )
        assert cache.add_many([title_only]) == 1
        assert cache.add_many([enriched]) == 1
        cache.write()
        loaded = SourceCache(path)
        [paper] = loaded.papers()
        assert paper.abstract == "kernel scheduling"
        assert paper.pdf_url == "https://example.com/p.pdf"
    finally:
        path.unlink(missing_ok=True)
