from __future__ import annotations

import os

import yaml

from paper_daily.models import Paper
from paper_daily.runner import bootstrap_source, filter_summarizable_papers, run


def test_dry_run_without_openai_key(tmp_path, monkeypatch) -> None:
    config = {
        "run": {"max_papers_per_day": 20, "lookback_days": 14, "timezone": "Asia/Shanghai", "require_openai_key": True},
        "storage": {
            "metadata_path": str(tmp_path / "data" / "papers.jsonl"),
            "source_cache_path": str(tmp_path / "data" / "source_cache.jsonl"),
            "summaries_dir": str(tmp_path / "summaries"),
        },
        "ranking": {"minimum_score": 1},
        "topics": [{"name": "systems", "keywords": ["kernel"]}],
        "sources": {"arxiv": {"enabled": False}, "openalex": {"enabled": False}, "dblp": {"enabled": False}, "usenix": {"enabled": False}},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert run(str(path), dry_run=True) == 0
    assert not (tmp_path / "summaries").exists()
    assert not (tmp_path / "data" / "source_cache.jsonl").exists()


def test_bootstrap_usenix_writes_source_cache_only(tmp_path, monkeypatch) -> None:
    config = {
        "storage": {
            "metadata_path": str(tmp_path / "data" / "papers.jsonl"),
            "source_cache_path": str(tmp_path / "data" / "source_cache.jsonl"),
            "summaries_dir": str(tmp_path / "summaries"),
        },
        "sources": {"usenix": {"enabled": True}},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(
        "paper_daily.runner.fetch_usenix",
        lambda _config, mode="weekly": [
            __import__("paper_daily.models", fromlist=["Paper"]).Paper(
                paper_id="usenix:1",
                title="Kernel Paper",
                source="usenix",
            )
        ],
    )

    assert bootstrap_source(str(path), "usenix") == 0
    assert (tmp_path / "data" / "source_cache.jsonl").exists()
    assert not (tmp_path / "data" / "papers.jsonl").exists()
    assert not (tmp_path / "summaries").exists()


def test_filter_skips_unpublished_usenix_by_default() -> None:
    papers = [
        Paper(paper_id="usenix:1", title="Title Only", source="usenix", raw={"has_public_content": False}),
        Paper(paper_id="usenix:2", title="Published", source="usenix", pdf_url="https://example.com/p.pdf", raw={"has_public_content": True}),
        Paper(paper_id="arxiv:1", title="Kernel", source="arxiv"),
    ]
    config = {"sources": {"usenix": {"include_unpublished": False}}}
    titles = [paper.title for paper in filter_summarizable_papers(papers, config)]
    assert titles == ["Published", "Kernel"]


def test_filter_can_include_unpublished_usenix() -> None:
    paper = Paper(paper_id="usenix:1", title="Title Only", source="usenix", raw={"has_public_content": False})
    config = {"sources": {"usenix": {"include_unpublished": True}}}
    assert filter_summarizable_papers([paper], config) == [paper]


def test_filter_skips_dblp_without_public_content_by_default() -> None:
    papers = [
        Paper(paper_id="dblp:1", title="Title Only", source="dblp"),
        Paper(paper_id="dblp:2", title="Abstract Paper", source="dblp", abstract="kernel scheduler"),
        Paper(paper_id="dblp:3", title="PDF Paper", source="dblp", pdf_url="https://example.com/p.pdf"),
    ]
    titles = [paper.title for paper in filter_summarizable_papers(papers, {"sources": {"dblp": {}}})]
    assert titles == ["Abstract Paper", "PDF Paper"]


def test_filter_can_include_title_only_dblp() -> None:
    paper = Paper(paper_id="dblp:1", title="Title Only", source="dblp")
    config = {"sources": {"dblp": {"require_public_content": False}}}
    assert filter_summarizable_papers([paper], config) == [paper]
