from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Paper:
    paper_id: str
    title: str
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    source: str = ""
    url: str = ""
    pdf_url: str = ""
    doi: str = ""
    venue: str = ""
    published_at: datetime | None = None
    updated_at: datetime | None = None
    topics: list[str] = field(default_factory=list)
    score: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["published_at"] = self.published_at.isoformat() if self.published_at else None
        data["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        data["stable_key"] = stable_key(self)
        return data


def stable_key(paper: Paper) -> str:
    doi = normalize_doi(paper.doi)
    if doi:
        return f"doi:{doi}"
    if paper.source == "arxiv" and paper.paper_id:
        return paper.paper_id.lower()
    return f"title:{normalize_title(paper.title)}"


def identity_keys(paper: Paper) -> set[str]:
    keys = {stable_key(paper)}
    normalized = normalize_title(paper.title)
    if normalized:
        keys.add(f"title:{normalized}")
    doi = normalize_doi(paper.doi)
    if doi:
        keys.add(f"doi:{doi}")
    return keys


def normalize_doi(value: str) -> str:
    doi = value.strip().lower()
    doi = doi.removeprefix("https://doi.org/")
    doi = doi.removeprefix("http://dx.doi.org/")
    doi = doi.removeprefix("doi:")
    return doi


def normalize_title(value: str) -> str:
    return " ".join(
        "".join(ch.lower() if ch.isalnum() else " " for ch in value).split()
    )
