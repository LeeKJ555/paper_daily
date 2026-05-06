from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from paper_daily.http import get_text
from paper_daily.models import Paper
from paper_daily.text import clean_text


BASE_URL = "https://www.usenix.org"


def fetch_usenix(config: dict, mode: str = "weekly") -> list[Paper]:
    source_config = config.get("sources", {}).get("usenix", {})
    if not source_config.get("enabled", False):
        return []

    events = source_config.get("events", ["osdi", "nsdi", "fast", "atc"])
    years_key = "bootstrap_years_back" if mode == "bootstrap" else "weekly_years_back"
    fallback_years = source_config.get("years_back", 3 if mode == "bootstrap" else 1)
    years_back = int(source_config.get(years_key, fallback_years))
    max_results = int(source_config.get("max_results", 120)) if mode == "weekly" else None
    max_per_event = int(source_config.get("max_results_per_event", 30)) if mode == "weekly" else None
    current_year = datetime.now().year
    papers: list[Paper] = []
    for event in events:
        event_papers: list[Paper] = []
        for year in range(current_year, current_year - years_back, -1):
            for slug in _event_slugs(event, year):
                url = f"{BASE_URL}/conference/{slug}/technical-sessions"
                try:
                    html = get_text(url)
                except Exception:
                    continue
                event_papers.extend(_parse_page(html, event, year, url))
                if max_per_event and len(event_papers) >= max_per_event:
                    break
            if max_per_event and len(event_papers) >= max_per_event:
                break
        papers.extend(event_papers[:max_per_event] if max_per_event else event_papers)
        if max_results and len(papers) >= max_results:
            return papers[:max_results]
    return papers[:max_results] if max_results else papers


def _event_slugs(event: str, year: int) -> list[str]:
    short = str(year)[-2:]
    if event == "atc":
        return [f"atc{short}", f"usenix-atc-{year}"]
    return [f"{event}{short}", f"{event}-{year}"]


def _parse_page(html: str, event: str, year: int, page_url: str) -> list[Paper]:
    soup = BeautifulSoup(html, "html.parser")
    papers: list[Paper] = []
    seen_urls: set[str] = set()
    for link in soup.select("a[href*='/presentation/']"):
        title = clean_text(link.get_text(" ", strip=True))
        if len(title) < 8:
            continue
        url = urljoin(BASE_URL, link.get("href", ""))
        if url in seen_urls:
            continue
        seen_urls.add(url)
        container = link.find_parent(["article", "div", "li"]) or link.parent
        text = clean_text(container.get_text(" ", strip=True) if container else "")
        pdf_link = container.select_one("a[href$='.pdf'], a[href*='/system/files/']") if container else None
        pdf_url = urljoin(BASE_URL, pdf_link.get("href", "")) if pdf_link else ""
        has_public_content = bool(pdf_url)
        papers.append(
            Paper(
                paper_id=f"usenix:{url}",
                title=title,
                abstract="",
                authors=[],
                source="usenix",
                url=url,
                pdf_url=pdf_url,
                venue=f"USENIX {event.upper()} {year}",
                published_at=datetime(year, 1, 1, tzinfo=timezone.utc),
                raw={
                    "event": event,
                    "has_public_content": has_public_content,
                    "listing_url": page_url,
                    "listing_text": text[:1000],
                    "publication_state": "published" if has_public_content else "title-only",
                },
            )
        )
    return papers
