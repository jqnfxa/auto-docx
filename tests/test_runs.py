import xml.etree.ElementTree as ET

from autodocx.ns import w_tag
from autodocx.runs import make_paragraph, make_run, parse_inline


def _runs_to_text(runs: list[ET.Element]) -> list[tuple[str, bool]]:
    out = []
    for r in runs:
        text = r.find(w_tag("t")).text or ""
        bold = r.find(f"{w_tag('rPr')}/{w_tag('b')}") is not None
        out.append((text, bold))
    return out


def test_parse_inline_splits_on_bold_markers():
    runs = parse_inline("plain **bold** plain")
    assert _runs_to_text(runs) == [("plain ", False), ("bold", True), (" plain", False)]


def test_parse_inline_handles_no_bold():
    runs = parse_inline("just text")
    assert _runs_to_text(runs) == [("just text", False)]


def test_parse_inline_handles_only_bold():
    runs = parse_inline("**only**")
    assert _runs_to_text(runs) == [("only", True)]


def test_make_paragraph_applies_style_and_alignment():
    p = make_paragraph("BodyText", [make_run("hi")], align="center")
    style = p.find(f"{w_tag('pPr')}/{w_tag('pStyle')}").get(w_tag("val"))
    jc = p.find(f"{w_tag('pPr')}/{w_tag('jc')}").get(w_tag("val"))
    assert style == "BodyText"
    assert jc == "center"


def test_make_paragraph_explicit_indent_overrides_style_default():
    p = make_paragraph("BodyText", [make_run("x")], ind_left=1418, ind_first_line=0)
    ind = p.find(f"{w_tag('pPr')}/{w_tag('ind')}")
    assert ind.get(w_tag("left")) == "1418"
    assert ind.get(w_tag("firstLine")) == "0"


def test_make_paragraph_heading_disables_numbering():
    p = make_paragraph("Heading2", [make_run("Title")])
    numpr = p.find(f"{w_tag('pPr')}/{w_tag('numPr')}")
    assert numpr is not None
    num_id = numpr.find(w_tag("numId")).get(w_tag("val"))
    assert num_id == "0"
