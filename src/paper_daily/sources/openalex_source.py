from __future__ import annotations

from datetime import datetime, timedelta, timezone

from paper_daily.http import get_json
from paper_daily.models import Paper, identity_keys
from paper_daily.text import clean_text


OPENALEX_WORKS = "https://api.openalex.org/works"
DEFAULT_QUERIES = [
    "operating system",
    "kernel",
    "tiered memory",
    "CXL memory",
    "distributed system",
    "storage system",
    "file system",
    "virtual memory",
]


def fetch_openalex(config: dict) -> list[Paper]:
    source_config = config.get("sources", {}).get("openalex", {})
    if not source_config.get("enabled", False):
        return []

    max_results = int(source_config.get("max_results", 100))
    max_queries = int(source_config.get("max_queries", 8))
    per_query = int(source_config.get("per_query", 25))
    from_date = (datetime.now(timezone.utc) - timedelta(days=int(config.get("run", {}).get("lookback_days", 14)))).date()
    queries = source_config.get("queries") or DEFAULT_QUERIES
    papers: list[Paper] = []
    seen: set[str] = set()
    for query in queries[:max_queries]:
        try:
            data = get_json(
                OPENALEX_WORKS,
                {
                    "search": query,
                    "filter": f"from_publication_date:{from_date.isoformat()}",
                    "per-page": min(per_query, 200),
                    "sort": "publication_date:desc",
                },
            )
        except Exception as exc:
            print(f"WARNING: openalex query {query!r} failed: {exc}")
            continue
        for item in data.get("results", []):
            paper = paper_from_openalex_item(item, query, source_config)
            if not paper:
                continue
            keys = identity_keys(paper)
            if keys & seen:
                continue
            seen.update(keys)
            papers.append(paper)
            if len(papers) >= max_results:
                return papers
    return papers


def paper_from_openalex_item(item: dict, query: str, source_config: dict, *, apply_filters: bool = True) -> Paper | None:
    title = clean_text(item.get("title") or item.get("display_name") or "")
    if not title or _looks_like_non_paper_title(title):
        return None
    abstract = clean_text(_abstract(item.get("abstract_inverted_index")))
    if apply_filters and not _passes_source_filters(title, abstract, source_config):
        return None
    location = item.get("primary_location") or {}
    source = location.get("source") or {}
    open_access = item.get("open_access") or {}
    pdf_url = location.get("pdf_url") or open_access.get("oa_url") or ""
    return Paper(
        paper_id=f"openalex:{item.get('id', title)}",
        title=title,
        abstract=abstract,
        authors=_authors(item.get("authorships", [])),
        source="openalex",
        url=item.get("doi") or item.get("id", ""),
        pdf_url=pdf_url or "",
        doi=(item.get("doi") or "").removeprefix("https://doi.org/"),
        venue=source.get("display_name", "") if isinstance(source, dict) else "",
        published_at=_parse_date(item.get("publication_date")),
        raw={
            "query": query,
            "openalex_id": item.get("id"),
            "cited_by_count": item.get("cited_by_count"),
            "open_access": open_access,
            "open_access_pdf": bool(pdf_url and open_access.get("is_oa")),
        },
    )


def _looks_like_non_paper_title(title: str) -> bool:
    lower = title.lower()
    return (
        len(title) > 260
        or lower.startswith("# ")
        or lower.startswith("proceedings of ")
        or " **document type:** " in lower
    )


def _passes_source_filters(title: str, abstract: str, source_config: dict) -> bool:
    text = f"{title} {abstract}".lower()
    for keyword in source_config.get("negative_keywords", []):
        if keyword.lower() in text:
            return False
    title_required = [keyword.lower() for keyword in source_config.get("title_required_keywords", [])]
    if title_required and not any(keyword in title.lower() for keyword in title_required):
        return False
    required = [keyword.lower() for keyword in source_config.get("required_context_keywords", [])]
    if not required:
        return True
    return any(keyword in text for keyword in required)


def _authors(authorships: list[dict]) -> list[str]:
    return [
        authorship.get("author", {}).get("display_name", "")
        for authorship in authorships
        if authorship.get("author", {}).get("display_name")
    ]


def _abstract(index: dict | None) -> str:
    if not index:
        return ""
    words: list[tuple[int, str]] = []
    for word, positions in index.items():
        for position in positions:
            words.append((int(position), word))
    return " ".join(word for _, word in sorted(words))


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
