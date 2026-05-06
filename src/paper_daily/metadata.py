from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Paper, identity_keys, stable_key


@dataclass(slots=True)
class PaperRecord:
    stable_key: str
    identity_keys: list[str]
    paper: dict[str, Any]
    summary_path: str
    run_date: str
    pdf_downloaded: bool = False
    fulltext_used: bool = False

    def to_json(self) -> str:
        return json.dumps(
            {
                "stable_key": self.stable_key,
                "identity_keys": self.identity_keys,
                "paper": self.paper,
                "summary_path": self.summary_path,
                "run_date": self.run_date,
                "pdf_downloaded": self.pdf_downloaded,
                "fulltext_used": self.fulltext_used,
            },
            ensure_ascii=False,
            sort_keys=True,
        )


class MetadataStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records = self._load()

    def seen_keys(self) -> set[str]:
        return set(self.records)

    def has_seen(self, paper: Paper) -> bool:
        return bool(identity_keys(paper) & set(self.records))

    def add(self, record: PaperRecord) -> None:
        keys = set(record.identity_keys) | {record.stable_key}
        record.identity_keys = sorted(keys)
        for key in record.identity_keys:
            self.records[key] = record

    def write(self) -> None:
        unique_records = {
            record.stable_key: record
            for record in self.records.values()
        }
        lines = [record.to_json() for record in unique_records.values()]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def _load(self) -> dict[str, PaperRecord]:
        if not self.path.exists():
            return {}
        records: dict[str, PaperRecord] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            record = PaperRecord(
                stable_key=raw["stable_key"],
                identity_keys=raw.get("identity_keys") or [raw["stable_key"]],
                paper=raw["paper"],
                summary_path=raw["summary_path"],
                run_date=raw["run_date"],
                pdf_downloaded=raw.get("pdf_downloaded", False),
                fulltext_used=raw.get("fulltext_used", False),
            )
            for key in set(record.identity_keys) | {record.stable_key}:
                records[key] = record
        return records
