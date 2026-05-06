from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


ENV_REF = re.compile(r"^\$\{([A-Z0-9_]+)(?::([^}]*))?\}$")


def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    load_dotenv()
    with Path(path).open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    return _expand_env(config)


def _expand_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, str):
        match = ENV_REF.match(value)
        if match:
            name, default = match.groups()
            return os.getenv(name, default or "")
    return value


def topic_keywords(config: dict[str, Any]) -> list[str]:
    keywords: list[str] = []
    for topic in config.get("topics", []):
        keywords.extend(topic.get("keywords", []))
    return keywords
