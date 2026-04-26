import xml.etree.ElementTree as ET
from pathlib import Path

from autodocx.citations import CitationResolver
from autodocx.ns import w_tag
from autodocx.renderer import (
    BULLET_INDENT_PER_LEVEL_TWIPS,
    BULLET_MARKERS,
    RenderContext,
    build_references_entries,
    render_blocks,
)


def _make_ctx(**kwargs) -> RenderContext:
    # Tests in this file never embed images, so pictures_dir's value is inert.
    return RenderContext(pictures_dir=Path(), **kwargs)


def _paragraph_text(p: ET.Element) -> str:
    return "".join(t.text or "" for t in p.findall(f".//{w_tag('t')}"))


def test_heading2_default_renders_left_aligned():
    blocks = [("heading2", "1 Глава")]
    [p] = render_blocks(blocks, _make_ctx())
    style = p.find(f"{w_tag('pPr')}/{w_tag('pStyle')}").get(w_tag("val"))
    assert style == "Heading2"
    # No jc element when not centered.
    assert p.find(f"{w_tag('pPr')}/{w_tag('jc')}") is None


def test_heading2_in_centered_set_renders_centered():
    blocks = [("heading2", "ВВЕДЕНИЕ")]
    [p] = render_blocks(blocks, _make_ctx(centered_headings=frozenset({"ВВЕДЕНИЕ"})))
    jc = p.find(f"{w_tag('pPr')}/{w_tag('jc')}")
    assert jc.get(w_tag("val")) == "center"


def test_heading2_title_page_renders_as_bodytext_centered_bold():
    blocks = [("heading2", "РЕФЕРАТ")]
    [p] = render_blocks(blocks, _make_ctx(title_pages=frozenset({"РЕФЕРАТ"})))
    style = p.find(f"{w_tag('pPr')}/{w_tag('pStyle')}").get(w_tag("val"))
    assert style == "BodyText"
    assert p.find(f"{w_tag('pPr')}/{w_tag('jc')}").get(w_tag("val")) == "center"
    assert p.find(f".//{w_tag('rPr')}/{w_tag('b')}") is not None


def test_first_heading_does_not_get_page_break_by_default():
    blocks = [("heading2", "First"), ("heading2", "Second")]
    p1, p2 = render_blocks(blocks, _make_ctx())
    assert p1.find(f"{w_tag('pPr')}/{w_tag('pageBreakBefore')}") is None
    assert p2.find(f"{w_tag('pPr')}/{w_tag('pageBreakBefore')}") is not None


def test_bullet_indent_increases_per_level():
    blocks = [("bullet", (0, "lvl0")), ("bullet", (1, "lvl1")), ("bullet", (2, "lvl2"))]
    paragraphs = render_blocks(blocks, _make_ctx())
    expected_indents = [
        BULLET_INDENT_PER_LEVEL_TWIPS,
        2 * BULLET_INDENT_PER_LEVEL_TWIPS,
        3 * BULLET_INDENT_PER_LEVEL_TWIPS,
    ]
    for p, expected in zip(paragraphs, expected_indents, strict=True):
        ind = p.find(f"{w_tag('pPr')}/{w_tag('ind')}")
        assert ind is not None
        assert int(ind.get(w_tag("left"))) == expected


def test_bullet_marker_rotates_with_level():
    blocks = [("bullet", (lvl, "x")) for lvl in range(len(BULLET_MARKERS))]
    paragraphs = render_blocks(blocks, _make_ctx())
    for lvl, p in enumerate(paragraphs):
        text = _paragraph_text(p)
        assert text.startswith(BULLET_MARKERS[lvl])


def test_references_marker_renders_entries_only_once(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text("@online{a, title = {Alpha}}\n", encoding="utf-8")
    citer = CitationResolver(bib)
    citer.collect_citations("[@a]")
    ctx = _make_ctx(citer=citer)

    blocks = [("references_marker", None), ("references_marker", None)]
    rendered = render_blocks(blocks, ctx)

    # One paragraph (one cited entry) the first time, nothing the second time.
    assert len(rendered) == 1
    assert ctx.references_rendered is True


def test_references_marker_without_citations_emits_nothing():
    blocks = [("references_marker", None)]
    rendered = render_blocks(blocks, _make_ctx())
    assert rendered == []


def test_build_references_entries_numbers_paragraphs(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@online{a, title = {Alpha}}\n@online{b, title = {Beta}}\n",
        encoding="utf-8",
    )
    citer = CitationResolver(bib)
    citer.collect_citations("[@a; @b]")
    paragraphs = build_references_entries(citer)
    assert len(paragraphs) == 2
    assert _paragraph_text(paragraphs[0]).startswith("1. ")
    assert _paragraph_text(paragraphs[1]).startswith("2. ")
