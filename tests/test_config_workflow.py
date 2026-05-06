from __future__ import annotations

from pathlib import Path

import yaml

from paper_daily.config import load_config
from paper_daily.runner import max_papers_per_run


def test_default_config_is_weekly() -> None:
    config = load_config("config.yaml")
    assert config["run"]["lookback_days"] == 7
    assert max_papers_per_run(config) == 20


def test_max_papers_per_run_falls_back_to_old_key() -> None:
    assert max_papers_per_run({"run": {"max_papers_per_day": 12}}) == 12


def test_workflow_runs_on_thursday_beijing() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/daily.yml").read_text(encoding="utf-8"))
    assert workflow[True]["schedule"][0]["cron"] == "0 23 * * 3"
