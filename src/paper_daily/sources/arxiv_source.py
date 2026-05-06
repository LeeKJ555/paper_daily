from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from paper_daily.http import get_text
from paper_daily.models import Paper
from paper_daily.text import clean_text


ARXIV_API = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


def fetch_arxiv(config: dict) -> list[Paper]:
    source_config = config.get("sources", {}).get("arxiv", {})
    if not source_config.get("enabled", False):
        return []

    categories = source_config.get("categories", ["cs.OS"])
    max_results = int(source_config.get("max_results", 100))
    query = " OR ".join(f"cat:{category}" for category in categories)
    xml = get_text(
        ARXIV_API,
        {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        },
    )
    root = ET.fromstring(xml)
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(config.get("run", {}).get("lookback_days", 14)))
    papers: list[Paper] = []
    for entry in root.findall(f"{ATOM}entry"):
        published = _parse_datetime(_text(entry, f"{ATOM}published"))
        if published and published < cutoff:
            continue
        url = _text(entry, f"{ATOM}id")
        arxiv_id = url.rsplit("/", 1)[-1] if url else _text(entry, f"{ATOM}title")
        pdf_url = ""
        for link in entry.findall(f"{ATOM}link"):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href", "")
                break
        categories_found = [node.attrib.get("term", "") for node in entry.findall(f"{ATOM}category")]
        doi = _text(entry, f"{ARXIV}doi")
        papers.append(
            Paper(
                paper_id=f"arxiv:{arxiv_id}",
                title=clean_text(_text(entry, f"{ATOM}title")),
                abstract=clean_text(_text(entry, f"{ATOM}summary")),
                authors=[
                    clean_text(_text(author, f"{ATOM}name"))
                    for author in entry.findall(f"{ATOM}author")
                ],
                source="arxiv",
                url=url,
                pdf_url=pdf_url,
                doi=doi,
                venue="arXiv " + ", ".join(filter(None, categories_found)),
                published_at=published,
                updated_at=_parse_datetime(_text(entry, f"{ATOM}updated")),
                raw={"categories": categories_found},
            )
        )
    return papers


def _text(node: ET.Element, path: str) -> str:
    found = node.find(path)
    return found.text if found is not None and found.text else ""


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
