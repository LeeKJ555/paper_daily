from __future__ import annotations

from paper_daily.enrichment import enrich_papers
from paper_daily.models import Paper


def _openalex_item(title: str = "Kernel Scheduling") -> dict:
    return {
        "id": "https://openalex.org/W1",
        "title": title,
        "doi": "https://doi.org/10.1/kernel",
        "publication_date": "2026-05-05",
        "abstract_inverted_index": {"kernel": [0], "scheduling": [1]},
        "authorships": [{"author": {"display_name": "Ada"}}],
        "primary_location": {"source": {"display_name": "OSDI"}, "pdf_url": "https://example.com/p.pdf"},
        "open_access": {"is_oa": True, "oa_url": "https://example.com/p.pdf"},
    }


def test_enriches_dblp_by_doi(monkeypatch) -> None:
    captured = []

    def fake_get_json(url, params=None):
        captured.append((url, params))
        return _openalex_item()

    monkeypatch.setattr("paper_daily.enrichment.get_json", fake_get_json)
    paper = Paper(paper_id="dblp:1", title="Kernel Scheduling", source="dblp", doi="10.1/kernel")
    enriched = enrich_papers(
        [paper],
        {"sources": {"dblp": {"enrich_with_openalex": True, "enrichment_max_queries": 10}}},
    )[0]

    assert "/doi:10.1/kernel" in captured[0][0]
    assert enriched.abstract == "kernel scheduling"
    assert enriched.pdf_url == "https://example.com/p.pdf"
    assert enriched.raw["enrichment_status"] == "matched"
    assert enriched.raw["open_access_pdf"] is True


def test_enriches_dblp_by_title_without_doi(monkeypatch) -> None:
    captured = []

    def fake_get_json(url, params=None):
        captured.append((url, params))
        return {"results": [_openalex_item("Kernel Scheduling")]}

    monkeypatch.setattr("paper_daily.enrichment.get_json", fake_get_json)
    paper = Paper(paper_id="dblp:1", title="Kernel Scheduling", source="dblp")
    enriched = enrich_papers(
        [paper],
        {"sources": {"dblp": {"enrich_with_openalex": True, "enrichment_max_queries": 10}}},
    )[0]

    assert captured[0][1]["search"] == "Kernel Scheduling"
    assert enriched.abstract == "kernel scheduling"
    assert enriched.raw["enrichment_match"] == "title"


def test_marks_unmatched_dblp_enrichment(monkeypatch) -> None:
    monkeypatch.setattr("paper_daily.enrichment.get_json", lambda *_args, **_kwargs: {"results": []})
    paper = Paper(paper_id="dblp:1", title="Missing Paper", source="dblp")
    enriched = enrich_papers(
        [paper],
        {"sources": {"dblp": {"enrich_with_openalex": True, "enrichment_max_queries": 10}}},
    )[0]

    assert enriched.abstract == ""
    assert enriched.pdf_url == ""
    assert enriched.raw["enrichment_status"] == "not-found"


def test_respects_dblp_enrichment_query_budget(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("paper_daily.enrichment.get_json", lambda *_args, **_kwargs: calls.append(1) or {"results": []})
    papers = [
        Paper(paper_id="dblp:1", title="One", source="dblp"),
        Paper(paper_id="dblp:2", title="Two", source="dblp"),
    ]
    enriched = enrich_papers(
        papers,
        {"sources": {"dblp": {"enrich_with_openalex": True, "enrichment_max_queries": 1}}},
    )

    assert len(calls) == 1
    assert enriched[1].raw["enrichment_status"] == "skipped-query-budget"


def test_doi_fallback_does_not_exceed_query_budget(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr("paper_daily.enrichment.get_json", lambda *_args, **_kwargs: calls.append(1) or {})
    paper = Paper(paper_id="dblp:1", title="Kernel Scheduling", source="dblp", doi="10.1/kernel")
    enriched = enrich_papers(
        [paper],
        {"sources": {"dblp": {"enrich_with_openalex": True, "enrichment_max_queries": 1}}},
    )[0]

    assert len(calls) == 1
    assert enriched.raw["enrichment_status"] == "skipped-query-budget"
