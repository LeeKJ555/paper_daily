from __future__ import annotations

from datetime import datetime, timezone

from paper_daily.http import get_json
from paper_daily.models import Paper, identity_keys
from paper_daily.text import clean_text


DBLP_API = "https://dblp.org/search/publ/api"


def fetch_dblp(config: dict) -> list[Paper]:
    source_config = config.get("sources", {}).get("dblp", {})
    if not source_config.get("enabled", False):
        return []

    venues = source_config.get("venues", [])
    max_results = int(source_config.get("max_results_per_venue", source_config.get("max_results_per_query", 50)))
    max_queries = int(source_config.get("max_queries", 12))
    years_back = int(source_config.get("years_back", 3))
    current_year = datetime.now().year
    papers: list[Paper] = []
    seen: set[str] = set()
    query_count = 0
    for year in range(current_year, current_year - years_back, -1):
        for venue in venues:
            if query_count >= max_queries:
                return papers
            query = f"{venue} {year}"
            query_count += 1
            try:
                data = get_json(DBLP_API, {"q": query, "format": "json", "h": max_results})
            except Exception as exc:
                print(f"WARNING: dblp query {query!r} failed: {exc}")
                continue
            hits = data.get("result", {}).get("hits", {}).get("hit", [])
            for hit in hits:
                paper = _paper_from_hit(hit, query, venue, year, source_config)
                if not paper:
                    continue
                keys = identity_keys(paper)
                if keys & seen:
                    continue
                seen.update(keys)
                papers.append(paper)
    return papers


def _paper_from_hit(hit: dict, query: str, fallback_venue: str, year: int, source_config: dict) -> Paper | None:
    info = hit.get("info", {})
    title = clean_text(info.get("title", "")).rstrip(".")
    if not title:
        return None
    if str(info.get("year", "")) != str(year):
        return None
    if not _venue_matches(info.get("venue", ""), fallback_venue):
        return None
    if _looks_like_non_paper_title(title):
        return None
    if not _passes_title_filter(title, source_config):
        return None
    return Paper(
        paper_id=f"dblp:{info.get('key', title)}",
        title=title,
        abstract="",
        authors=_authors(info.get("authors", {})),
        source="dblp",
        url=info.get("url", ""),
        pdf_url="",
        doi=info.get("doi", ""),
        venue=info.get("venue", fallback_venue),
        published_at=_year(info.get("year")),
        raw={"query": query, "type": info.get("type"), "year": info.get("year")},
    )


def _looks_like_non_paper_title(title: str) -> bool:
    lower = title.lower()
    return (
        len(title) > 260
        or lower.startswith("proceedings of ")
        or " symposium on " in lower and ", " in title and any(char.isdigit() for char in title)
        or " conference on " in lower and ", " in title and any(char.isdigit() for char in title)
        or " workshop on " in lower and ", " in title and any(char.isdigit() for char in title)
    )


def _authors(raw: dict) -> list[str]:
    authors = raw.get("author", [])
    if isinstance(authors, dict):
        authors = [authors]
    return [item.get("text", "") for item in authors if item.get("text")]


def _venue_matches(actual: str, expected: str) -> bool:
    actual_norm = _normalize_venue(actual)
    aliases = {
        "USENIX ATC": ["USENIX ATC", "USENIX Annual Technical Conference"],
    }
    candidates = aliases.get(expected, [expected])
    return any(_normalize_venue(candidate) == actual_norm for candidate in candidates)


def _normalize_venue(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _passes_title_filter(title: str, source_config: dict) -> bool:
    keywords = source_config.get("title_required_keywords", [])
    if not keywords:
        return True
    lower = title.lower()
    return any(keyword.lower() in lower for keyword in keywords)


def _year(value: str | int | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime(int(value), 1, 1, tzinfo=timezone.utc)
    except ValueError:
        return None
