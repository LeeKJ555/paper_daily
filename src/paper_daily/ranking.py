from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .models import Paper, identity_keys


def dedupe_papers(papers: list[Paper]) -> list[Paper]:
    seen: set[str] = set()
    unique: list[Paper] = []
    for paper in papers:
        keys = identity_keys(paper)
        if keys & seen:
            continue
        seen.update(keys)
        unique.append(paper)
    return unique


def rank_papers(papers: list[Paper], config: dict) -> list[Paper]:
    weights = config.get("ranking", {})
    minimum_score = int(weights.get("minimum_score", 1))
    arxiv_minimum_score = int(weights.get("arxiv_minimum_score", minimum_score))
    title_weight = int(weights.get("title_weight", 4))
    abstract_weight = int(weights.get("abstract_weight", 1))
    venue_weight = int(weights.get("venue_weight", 3))
    pdf_weight = int(weights.get("pdf_weight", 2))
    recent_weight = int(weights.get("recent_weight", 2))
    negative_keyword_weight = int(weights.get("negative_keyword_weight", 0))
    recent_cutoff = datetime.now(timezone.utc) - timedelta(days=int(config.get("run", {}).get("lookback_days", 14)))
    negative_keywords = [keyword.lower() for keyword in weights.get("negative_keywords", [])]
    arxiv_required_keywords = [keyword.lower() for keyword in weights.get("arxiv_required_keywords", [])]

    venue_terms = {
        venue.lower()
        for venue in config.get("sources", {}).get("dblp", {}).get("venues", [])
    }

    for paper in papers:
        title = paper.title.lower()
        abstract = paper.abstract.lower()
        venue = paper.venue.lower()
        score = 0
        topics: set[str] = set()

        for topic in config.get("topics", []):
            topic_name = topic.get("name", "topic")
            for keyword in topic.get("keywords", []):
                needle = keyword.lower()
                if needle in title:
                    score += title_weight
                    topics.add(topic_name)
                if needle in abstract:
                    score += abstract_weight
                    topics.add(topic_name)

        if venue and any(term in venue for term in venue_terms):
            score += venue_weight
        if paper.pdf_url:
            score += pdf_weight
        if paper.published_at and paper.published_at >= recent_cutoff:
            score += recent_weight
        for keyword in negative_keywords:
            if keyword and (keyword in title or keyword in abstract):
                score -= negative_keyword_weight

        paper.score = score
        paper.topics = sorted(topics)

    ranked = [
        paper
        for paper in papers
        if _passes_thresholds(paper, minimum_score, arxiv_minimum_score, arxiv_required_keywords)
    ]
    return sorted(
        ranked,
        key=lambda paper: (
            paper.score,
            paper.published_at.isoformat() if paper.published_at else "",
            paper.title.lower(),
        ),
        reverse=True,
    )


def _passes_thresholds(
    paper: Paper,
    minimum_score: int,
    arxiv_minimum_score: int,
    arxiv_required_keywords: list[str],
) -> bool:
    if paper.source != "arxiv":
        return paper.score >= minimum_score
    if paper.score < arxiv_minimum_score:
        return False
    if not arxiv_required_keywords:
        return True
    text = f"{paper.title} {paper.abstract}".lower()
    return any(keyword in text for keyword in arxiv_required_keywords)
