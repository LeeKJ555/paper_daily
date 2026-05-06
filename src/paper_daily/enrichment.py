from __future__ import annotations

from dataclasses import replace
from urllib.parse import quote

from .http import get_json
from .models import Paper, normalize_doi
from .sources.openalex_source import OPENALEX_WORKS, paper_from_openalex_item
from .text import clean_text


def enrich_papers(papers: list[Paper], config: dict) -> list[Paper]:
    source_config = config.get("sources", {}).get("dblp", {})
    if not source_config.get("enrich_with_openalex", False):
        return papers

    max_queries = int(source_config.get("enrichment_max_queries", 40))
    enriched: list[Paper] = []
    query_count = 0
    for paper in papers:
        if paper.source != "dblp":
            enriched.append(paper)
            continue
        if query_count >= max_queries:
            enriched.append(_mark_enrichment(paper, "skipped-query-budget"))
            continue
        try:
            enriched_paper, queries_used = enrich_dblp_with_openalex(paper, max_queries - query_count)
            query_count += queries_used
            enriched.append(enriched_paper)
        except Exception as exc:
            query_count += 1
            print(f"WARNING: dblp enrichment failed for {paper.title!r}: {exc}")
            enriched.append(_mark_enrichment(paper, "error"))
    return enriched


def enrich_dblp_with_openalex(paper: Paper, query_budget: int) -> tuple[Paper, int]:
    queries_used = 0
    doi = normalize_doi(paper.doi)
    if doi and queries_used < query_budget:
        item = _lookup_openalex_by_doi(doi)
        queries_used += 1
        if item:
            return _merge_openalex(paper, item, "doi"), queries_used

    if paper.title and queries_used < query_budget:
        data = get_json(
            OPENALEX_WORKS,
            {
                "search": paper.title,
                "per-page": 3,
                "sort": "relevance_score:desc",
            },
        )
        queries_used += 1
        for item in data.get("results", []):
            if _titles_match(paper.title, item.get("title") or item.get("display_name") or ""):
                return _merge_openalex(paper, item, "title"), queries_used
        return _mark_enrichment(paper, "not-found"), queries_used

    status = "skipped-query-budget" if query_budget <= queries_used and paper.title else "not-found"
    return _mark_enrichment(paper, status), queries_used


def _lookup_openalex_by_doi(doi: str) -> dict | None:
    data = get_json(f"{OPENALEX_WORKS}/doi:{quote(doi, safe=':/')}")
    return data if data.get("id") else None


def _merge_openalex(paper: Paper, item: dict, match: str) -> Paper:
    openalex_paper = paper_from_openalex_item(item, f"dblp-enrichment-{match}", {}, apply_filters=False)
    if not openalex_paper:
        return _mark_enrichment(paper, "not-found")
    raw = {
        **paper.raw,
        "enriched_by": "openalex",
        "enrichment_status": "matched",
        "enrichment_match": match,
        "openalex_id": openalex_paper.raw.get("openalex_id"),
        "open_access": openalex_paper.raw.get("open_access"),
        "open_access_pdf": bool(openalex_paper.pdf_url and openalex_paper.raw.get("open_access", {}).get("is_oa")),
        "cited_by_count": openalex_paper.raw.get("cited_by_count"),
    }
    return replace(
        paper,
        abstract=paper.abstract or openalex_paper.abstract,
        doi=paper.doi or openalex_paper.doi,
        url=openalex_paper.url or paper.url,
        pdf_url=openalex_paper.pdf_url or paper.pdf_url,
        venue=paper.venue or openalex_paper.venue,
        published_at=paper.published_at or openalex_paper.published_at,
        raw=raw,
    )


def _mark_enrichment(paper: Paper, status: str) -> Paper:
    return replace(paper, raw={**paper.raw, "enriched_by": "openalex", "enrichment_status": status})


def _titles_match(left: str, right: str) -> bool:
    return clean_text(left).casefold().rstrip(".") == clean_text(right).casefold().rstrip(".")
