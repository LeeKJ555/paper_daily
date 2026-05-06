from __future__ import annotations

import re
import unicodedata


def clean_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", " ", normalized).strip()


def slugify(value: str, max_length: int = 90) -> str:
    value = unicodedata.normalize("NFKD", value)
    slug = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", value).strip("-").lower()
    return slug[:max_length].strip("-") or "paper"
