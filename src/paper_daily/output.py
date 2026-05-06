from __future__ import annotations

from pathlib import Path

from .models import Paper, stable_key
from .text import slugify


def summary_filename(paper: Paper) -> str:
    key = slugify(stable_key(paper), 50)
    title = slugify(paper.title, 80)
    return f"{key}-{title}.md"


def write_summary(summaries_dir: str | Path, run_date: str, paper: Paper, markdown: str) -> Path:
    day_dir = Path(summaries_dir) / run_date
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / summary_filename(paper)
    path.write_text(markdown.strip() + "\n", encoding="utf-8")
    return path


def write_index(summaries_dir: str | Path, run_date: str, papers: list[tuple[Paper, Path]]) -> Path:
    day_dir = Path(summaries_dir) / run_date
    day_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Paper Daily - {run_date}",
        "",
        f"今日新增 {len(papers)} 篇 OS/System 方向论文总结。",
        "",
    ]
    for idx, (paper, path) in enumerate(papers, start=1):
        topics = ", ".join(paper.topics) if paper.topics else "N/A"
        link = path.name
        lines.extend(
            [
                f"## {idx}. {paper.title}",
                "",
                f"- 总结: [{path.name}]({link})",
                f"- 来源: {paper.source}",
                f"- 主题: {topics}",
                f"- 分数: {paper.score}",
                f"- Venue: {paper.venue or 'N/A'}",
                f"- DOI: {paper.doi or 'N/A'}",
                f"- 原文: {paper.url or paper.pdf_url or 'N/A'}",
                "",
            ]
        )
    path = day_dir / "index.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
