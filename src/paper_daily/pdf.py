from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import fitz
import httpx

from .models import Paper, stable_key
from .text import clean_text, slugify


OPEN_ACCESS_SOURCES = {"arxiv", "usenix", "openalex"}


def is_allowed_pdf(paper: Paper) -> bool:
    if not paper.pdf_url:
        return False
    if paper.source in OPEN_ACCESS_SOURCES:
        return True
    if paper.raw.get("open_access_pdf"):
        return True
    host = urlparse(paper.pdf_url).netloc.lower()
    return any(host.endswith(domain) for domain in ("arxiv.org", "usenix.org"))


def download_pdf(paper: Paper, cache_dir: str | Path, max_mb: int = 30) -> Path | None:
    if not is_allowed_pdf(paper):
        return None

    target_dir = Path(cache_dir) / "pdfs"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{slugify(stable_key(paper), 120)}.pdf"
    if target.exists() and target.stat().st_size > 0:
        return target

    max_bytes = max_mb * 1024 * 1024
    headers = {"User-Agent": "paper-daily/0.1 (+https://github.com/)"}
    try:
        with httpx.stream("GET", paper.pdf_url, headers=headers, timeout=60, follow_redirects=True) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "pdf" not in content_type and not paper.pdf_url.lower().endswith(".pdf"):
                return None
            total = 0
            with target.open("wb") as handle:
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        target.unlink(missing_ok=True)
                        return None
                    handle.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        return None
    return target


def extract_pdf_text(path: str | Path, max_chars: int) -> str:
    try:
        doc = fitz.open(Path(path))
    except Exception:
        return ""

    chunks: list[str] = []
    try:
        for page in doc:
            chunks.append(page.get_text("text"))
            if sum(len(chunk) for chunk in chunks) >= max_chars:
                break
    finally:
        doc.close()
    return clean_text("\n".join(chunks))[:max_chars]


def focused_excerpt(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    section_terms = [
        "abstract",
        "introduction",
        "design",
        "implementation",
        "evaluation",
        "experiment",
        "conclusion",
        "摘要",
        "引言",
        "设计",
        "实现",
        "评估",
        "实验",
        "结论",
    ]
    lower = text.lower()
    spans: list[str] = []
    window = max(1200, max_chars // max(len(section_terms), 1))
    for term in section_terms:
        index = lower.find(term.lower())
        if index >= 0:
            prefix = min(300, max_chars // 10)
            start = max(0, index - prefix)
            end = min(len(text), index + window)
            spans.append(text[start:end])
    if not spans:
        return text[:max_chars]
    excerpt = clean_text("\n\n".join(spans))
    return excerpt[:max_chars]
