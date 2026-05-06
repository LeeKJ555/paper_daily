from __future__ import annotations

import fitz

from paper_daily.models import Paper
from paper_daily.pdf import extract_pdf_text, focused_excerpt, is_allowed_pdf


def test_extract_pdf_text(tmp_path) -> None:
    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Abstract Kernel scheduling evaluation conclusion")
    doc.save(path)
    doc.close()

    text = extract_pdf_text(path, 1000)
    assert "Kernel scheduling" in text


def test_focused_excerpt_prefers_sections() -> None:
    text = "noise " * 1000 + "Introduction Important design details. " + "tail " * 1000
    excerpt = focused_excerpt(text, 200)
    assert "Introduction" in excerpt


def test_dblp_pdf_allowed_only_when_marked_open_access() -> None:
    paper = Paper(paper_id="dblp:1", title="Paper", source="dblp", pdf_url="https://example.com/p.pdf")
    assert not is_allowed_pdf(paper)
    paper.raw["open_access_pdf"] = True
    assert is_allowed_pdf(paper)
