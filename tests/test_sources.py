from __future__ import annotations

import pytest

from paper_daily.sources.arxiv_source import fetch_arxiv
from paper_daily.sources.dblp_source import fetch_dblp
from paper_daily.sources.openalex_source import fetch_openalex
from paper_daily.sources.usenix_source import fetch_usenix


def test_arxiv_parser(monkeypatch) -> None:
    xml = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2501.00001v1</id>
        <updated>2026-05-05T00:00:00Z</updated>
        <published>2026-05-05T00:00:00Z</published>
        <title>CXL Memory Tiering in Operating Systems</title>
        <summary>This paper studies tiered memory for OS kernels.</summary>
        <author><name>Alice</name></author>
        <category term="cs.OS"/>
        <link title="pdf" href="https://arxiv.org/pdf/2501.00001"/>
      </entry>
    </feed>"""
    monkeypatch.setattr("paper_daily.sources.arxiv_source.get_text", lambda *_args, **_kwargs: xml)
    papers = fetch_arxiv({"run": {"lookback_days": 1000}, "sources": {"arxiv": {"enabled": True}}})
    assert len(papers) == 1
    assert papers[0].source == "arxiv"
    assert papers[0].pdf_url


def test_openalex_parser(monkeypatch) -> None:
    captured = []

    data = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "Kernel Isolation",
                "doi": "https://doi.org/10.1/k",
                "publication_date": "2026-05-05",
                "abstract_inverted_index": {"kernel": [0], "isolation": [1]},
                "authorships": [{"author": {"display_name": "Bob"}}],
                "primary_location": {"source": {"display_name": "OSDI"}, "pdf_url": "https://example.com/a.pdf"},
                "open_access": {"oa_url": "https://example.com/a.pdf"},
            }
        ]
    }

    def fake_get_json(_url, params):
        captured.append(params)
        return data

    monkeypatch.setattr("paper_daily.sources.openalex_source.get_json", fake_get_json)
    config = {
        "run": {"lookback_days": 10},
        "topics": [],
        "sources": {
            "openalex": {
                "enabled": True,
                "queries": ["kernel", "tiered memory"],
                "max_queries": 2,
                "max_results": 10,
                "required_context_keywords": ["kernel"],
            }
        },
    }
    papers = fetch_openalex(config)
    assert len(papers) == 1
    assert papers[0].doi == "10.1/k"
    assert papers[0].abstract == "kernel isolation"
    assert [params["search"] for params in captured] == ["kernel", "tiered memory"]
    assert all("proceedings-article" not in params["filter"] for params in captured)


def test_openalex_skips_non_paper_titles(monkeypatch) -> None:
    data = {
        "results": [
            {"id": "bad", "title": "# " + "Long Document " * 40, "publication_date": "2026-05-05"},
            {"id": "good", "title": "Kernel Paper", "publication_date": "2026-05-05"},
        ]
    }
    monkeypatch.setattr("paper_daily.sources.openalex_source.get_json", lambda *_args, **_kwargs: data)
    config = {
        "run": {"lookback_days": 10},
        "sources": {"openalex": {"enabled": True, "queries": ["kernel"], "max_queries": 1}},
    }
    assert [paper.title for paper in fetch_openalex(config)] == ["Kernel Paper"]


def test_openalex_applies_context_and_negative_filters(monkeypatch) -> None:
    data = {
        "results": [
            {"id": "bad", "title": "A Gravitational Kernel for Galaxy Rotation Curves", "publication_date": "2026-05-05"},
            {"id": "good", "title": "Kernel Scheduling for Operating Systems", "publication_date": "2026-05-05"},
        ]
    }
    monkeypatch.setattr("paper_daily.sources.openalex_source.get_json", lambda *_args, **_kwargs: data)
    config = {
        "run": {"lookback_days": 10},
        "sources": {
            "openalex": {
                "enabled": True,
                "queries": ["kernel"],
                "max_queries": 1,
                "required_context_keywords": ["operating system"],
                "negative_keywords": ["gravitational", "galaxy"],
            }
        },
    }
    assert [paper.title for paper in fetch_openalex(config)] == ["Kernel Scheduling for Operating Systems"]


def test_openalex_applies_title_prefilter(monkeypatch) -> None:
    data = {
        "results": [
            {
                "id": "bad",
                "title": "Coastal and Regional Ocean COmmunity model",
                "abstract_inverted_index": {"storage": [0]},
                "publication_date": "2026-05-05",
            },
            {
                "id": "good",
                "title": "CXL Storage Systems",
                "abstract_inverted_index": {"storage": [0]},
                "publication_date": "2026-05-05",
            },
        ]
    }
    monkeypatch.setattr("paper_daily.sources.openalex_source.get_json", lambda *_args, **_kwargs: data)
    config = {
        "run": {"lookback_days": 10},
        "sources": {
            "openalex": {
                "enabled": True,
                "queries": ["storage"],
                "max_queries": 1,
                "title_required_keywords": ["CXL", "kernel", "file system"],
                "required_context_keywords": ["storage"],
            }
        },
    }
    assert [paper.title for paper in fetch_openalex(config)] == ["CXL Storage Systems"]


def test_dblp_parser(monkeypatch) -> None:
    captured = []
    data = {
        "result": {
            "hits": {
                "hit": [
                    {
                        "info": {
                            "key": "conf/osdi/x",
                            "title": "A Storage System.",
                            "authors": {"author": {"text": "Carol"}},
                            "venue": "OSDI",
                            "year": "2025",
                            "doi": "10.1/s",
                            "url": "https://dblp.org/rec/conf/osdi/x",
                        }
                    }
                ]
            }
        }
    }

    def fake_get_json(_url, params):
        captured.append(params)
        return data

    monkeypatch.setattr("paper_daily.sources.dblp_source.get_json", fake_get_json)
    config = {"topics": [], "sources": {"dblp": {"enabled": True, "venues": ["OSDI"], "years_back": 1, "max_queries": 1}}}
    papers = fetch_dblp(config)
    assert papers[0].title == "A Storage System"
    assert papers[0].authors == ["Carol"]
    assert captured[0]["q"].startswith("OSDI ")
    assert "operating system" not in captured[0]["q"]


def test_dblp_requires_matching_venue_and_year(monkeypatch) -> None:
    data = {
        "result": {
            "hits": {
                "hit": [
                    {"info": {"title": "Climate Simulation.", "venue": "ICLR", "year": "2026"}},
                    {"info": {"title": "Old Kernel Paper.", "venue": "OSDI", "year": "2025"}},
                    {"info": {"title": "Kernel Paper.", "venue": "OSDI", "year": "2026"}},
                ]
            }
        }
    }
    monkeypatch.setattr("paper_daily.sources.dblp_source.get_json", lambda *_args, **_kwargs: data)
    config = {"sources": {"dblp": {"enabled": True, "venues": ["OSDI"], "years_back": 1, "max_queries": 1}}}
    assert [paper.title for paper in fetch_dblp(config)] == ["Kernel Paper"]


def test_dblp_applies_title_prefilter(monkeypatch) -> None:
    data = {
        "result": {
            "hits": {
                "hit": [
                    {"info": {"title": "Efficient Tensor Computation.", "venue": "ASPLOS", "year": "2026"}},
                    {"info": {"title": "CXL Memory for Operating Systems.", "venue": "ASPLOS", "year": "2026"}},
                ]
            }
        }
    }
    monkeypatch.setattr("paper_daily.sources.dblp_source.get_json", lambda *_args, **_kwargs: data)
    config = {
        "sources": {
            "dblp": {
                "enabled": True,
                "venues": ["ASPLOS"],
                "years_back": 1,
                "max_queries": 1,
                "title_required_keywords": ["CXL", "operating system"],
            }
        }
    }
    assert [paper.title for paper in fetch_dblp(config)] == ["CXL Memory for Operating Systems"]


def test_dblp_respects_query_budget(monkeypatch) -> None:
    captured = []
    monkeypatch.setattr(
        "paper_daily.sources.dblp_source.get_json",
        lambda _url, params: captured.append(params) or {"result": {"hits": {"hit": []}}},
    )
    config = {
        "sources": {
            "dblp": {
                "enabled": True,
                "venues": ["OSDI", "NSDI", "FAST"],
                "years_back": 3,
                "max_queries": 2,
            }
        }
    }
    assert fetch_dblp(config) == []
    assert len(captured) == 2


def test_dblp_skips_proceedings_volumes(monkeypatch) -> None:
    data = {
        "result": {
            "hits": {
                "hit": [
                    {"info": {"title": "Proceedings of the ACM SIGOPS 31st Symposium on Operating Systems Principles", "venue": "SOSP", "year": "2025"}},
                    {"info": {"title": "19th USENIX Symposium on Operating Systems Design and Implementation, OSDI 2025, Boston, MA, USA, July 7-9, 2025", "venue": "OSDI", "year": "2025"}},
                    {"info": {"title": "Kernel Paper.", "venue": "SOSP", "year": "2025"}},
                ]
            }
        }
    }
    monkeypatch.setattr("paper_daily.sources.dblp_source.get_json", lambda *_args, **_kwargs: data)
    config = {"sources": {"dblp": {"enabled": True, "venues": ["SOSP"], "years_back": 1, "max_queries": 1}}}
    papers = fetch_dblp(config)
    assert [paper.title for paper in papers] == ["Kernel Paper"]


def test_usenix_weekly_respects_max_results(monkeypatch) -> None:
    html = """
    <html><body>
      <article><a href="/conference/osdi26/presentation/a">Kernel Paper A</a></article>
      <article><a href="/conference/osdi26/presentation/b">Kernel Paper B</a></article>
    </body></html>
    """
    monkeypatch.setattr("paper_daily.sources.usenix_source.get_text", lambda _url: html)
    config = {
        "sources": {
            "usenix": {
                "enabled": True,
                "events": ["osdi"],
                "weekly_years_back": 1,
                "bootstrap_years_back": 3,
                "max_results": 1,
            }
        }
    }
    assert len(fetch_usenix(config, mode="weekly")) == 1
    assert len(fetch_usenix(config, mode="bootstrap")) > 1


def test_usenix_weekly_limits_each_event(monkeypatch) -> None:
    html = """
    <html><body>
      <article><a href="/conference/event/presentation/a">Kernel Paper A</a></article>
      <article><a href="/conference/event/presentation/b">Kernel Paper B</a></article>
    </body></html>
    """
    monkeypatch.setattr("paper_daily.sources.usenix_source.get_text", lambda _url: html)
    config = {
        "sources": {
            "usenix": {
                "enabled": True,
                "events": ["osdi", "nsdi"],
                "weekly_years_back": 1,
                "max_results": 10,
                "max_results_per_event": 1,
            }
        }
    }
    papers = fetch_usenix(config, mode="weekly")
    assert len(papers) == 2
    assert {paper.raw["event"] for paper in papers} == {"osdi", "nsdi"}
