from __future__ import annotations

import os
from textwrap import dedent

from openai import OpenAI

from .models import Paper


REQUIRED_SECTIONS = [
    "论文针对什么问题",
    "提出了什么解决方案",
    "具体是怎么做的",
    "取得了什么效果",
    "旁观者视角的问题与不足",
    "值得继续追踪的点",
    "元数据与链接",
]


def summarize_paper(paper: Paper, config: dict, fulltext_excerpt: str = "") -> str:
    summary_config = config.get("summary", {})
    api_key_env = summary_config.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.getenv(api_key_env)
    if not api_key:
        if config.get("run", {}).get("require_openai_key", True):
            raise RuntimeError(f"{api_key_env} is required for paper-daily run.")
        return placeholder_summary(paper, fulltext_excerpt)

    provider = summary_config.get("provider", "openai")
    model = summary_config.get("model", "gpt-4o-mini")
    base_url = summary_config.get("base_url") or None
    max_input_chars = int(summary_config.get("max_input_chars", 42000))
    prompt = build_prompt(paper, fulltext_excerpt, max_input_chars)
    if provider == "openai":
        return summarize_with_openai_responses(api_key, model, prompt, base_url)
    if provider == "openai-compatible":
        return summarize_with_openai_compatible_chat(api_key, model, prompt, base_url)
    raise ValueError(f"Unsupported summary provider: {provider}")


def summarize_with_openai_responses(
    api_key: str,
    model: str,
    prompt: str,
    base_url: str | None = None,
) -> str:
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": (
                    "你是一名系统方向论文阅读助手。请用中文、客观、结构化地总结论文。"
                    "不得编造信息；如果正文或摘要没有给出实验细节，必须明确说明信息不足。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    return response.output_text.strip()


def summarize_with_openai_compatible_chat(
    api_key: str,
    model: str,
    prompt: str,
    base_url: str | None,
) -> str:
    if not base_url:
        raise ValueError("summary.base_url is required for openai-compatible provider.")
    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一名系统方向论文阅读助手。请用中文、客观、结构化地总结论文。"
                    "不得编造信息；如果正文或摘要没有给出实验细节，必须明确说明信息不足。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content
    return (content or "").strip()


def build_prompt(paper: Paper, fulltext_excerpt: str, max_chars: int) -> str:
    authors = ", ".join(paper.authors[:20]) if paper.authors else "N/A"
    content = dedent(
        f"""
        请为下面论文生成一份中文 Markdown 总结。

        必须包含以下二级标题，且顺序保持一致：
        {chr(10).join(f"## {section}" for section in REQUIRED_SECTIONS)}

        写作要求：
        - 面向 OS/System 方向研究和工程读者。
        - 优先解释问题、系统设计、关键机制、评估指标和局限。
        - 对“旁观者视角的问题与不足”给出具体观察，不要泛泛而谈。
        - 不要编造正文/摘要没有的信息。
        - 如果信息不足，写“原文摘录/摘要未提供足够信息”。

        元数据：
        标题：{paper.title}
        作者：{authors}
        来源：{paper.source}
        Venue：{paper.venue or "N/A"}
        DOI：{paper.doi or "N/A"}
        原文链接：{paper.url or "N/A"}
        PDF链接：{paper.pdf_url or "N/A"}
        匹配主题：{", ".join(paper.topics) or "N/A"}
        相关性分数：{paper.score}

        摘要：
        {paper.abstract or "N/A"}

        开放 PDF 正文摘录：
        {fulltext_excerpt or "N/A"}
        """
    ).strip()
    return content[:max_chars]


def placeholder_summary(paper: Paper, fulltext_excerpt: str = "") -> str:
    sections = "\n\n".join(
        f"## {section}\n\n待生成。当前未配置 `OPENAI_API_KEY`。"
        for section in REQUIRED_SECTIONS
        if section != "元数据与链接"
    )
    return dedent(
        f"""
        # {paper.title}

        {sections}

        ## 元数据与链接

        - 来源: {paper.source}
        - Venue: {paper.venue or "N/A"}
        - DOI: {paper.doi or "N/A"}
        - 原文: {paper.url or "N/A"}
        - PDF: {paper.pdf_url or "N/A"}
        - 主题: {", ".join(paper.topics) or "N/A"}
        - 分数: {paper.score}

        ## 原始摘要

        {paper.abstract or "N/A"}

        ## 正文摘录状态

        {"已提取开放 PDF 正文摘录。" if fulltext_excerpt else "未提取到开放 PDF 正文。"}
        """
    ).strip()
