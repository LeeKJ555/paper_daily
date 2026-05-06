from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import Paper, identity_keys, stable_key


class SourceCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records = self._load()

    def has_seen(self, paper: Paper) -> bool:
        return bool(identity_keys(paper) & set(self.records))

    def add_many(self, papers: Iterable[Paper]) -> int:
        changed = 0
        for paper in papers:
            if self.has_seen(paper):
                if self._refresh_if_more_complete(paper):
                    changed += 1
                continue
            record = paper.to_dict()
            record["identity_keys"] = sorted(identity_keys(paper))
            keys = set(record["identity_keys"]) | {stable_key(paper)}
            for key in keys:
                self.records[key] = record
            changed += 1
        return changed

    def _refresh_if_more_complete(self, paper: Paper) -> bool:
        keys = identity_keys(paper) & set(self.records)
        if not keys:
            return False
        current = self.records[next(iter(keys))]
        if _content_score(paper.to_dict()) <= _content_score(current):
            return False
        record = paper.to_dict()
        record["identity_keys"] = sorted(identity_keys(paper))
        for key in set(record["identity_keys"]) | {stable_key(paper)}:
            self.records[key] = record
        return True

    def papers(self) -> list[Paper]:
        unique = {
            record["stable_key"]: record
            for record in self.records.values()
            if record.get("stable_key")
        }
        return [_paper_from_record(record) for record in unique.values()]

    def write(self) -> None:
        unique = {
            record["stable_key"]: record
            for record in self.records.values()
            if record.get("stable_key")
        }
        lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in unique.values()]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        records: dict[str, dict] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            keys = set(record.get("identity_keys") or []) | {record.get("stable_key", "")}
            for key in filter(None, keys):
                records[key] = record
        return records


def _paper_from_record(record: dict) -> Paper:
    from datetime import datetime

    def parse_dt(value: str | None):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    return Paper(
        paper_id=record.get("paper_id", ""),
        title=record.get("title", ""),
        abstract=record.get("abstract", ""),
        authors=record.get("authors", []),
        source=record.get("source", ""),
        url=record.get("url", ""),
        pdf_url=record.get("pdf_url", ""),
        doi=record.get("doi", ""),
        venue=record.get("venue", ""),
        published_at=parse_dt(record.get("published_at")),
        updated_at=parse_dt(record.get("updated_at")),
        topics=record.get("topics", []),
        score=record.get("score", 0),
        raw=record.get("raw", {}),
    )


def _content_score(record: dict) -> int:
    return int(bool(record.get("abstract"))) + int(bool(record.get("pdf_url"))) * 2
