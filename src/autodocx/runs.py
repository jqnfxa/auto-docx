"""Build w:r (runs) and w:p (paragraphs)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from autodocx.ns import XML_SPACE, w_tag

_HEADING_STYLES = ("Heading1", "Heading2", "Heading3", "Heading4")
_BOLD_PATTERN = re.compile(r"(\*\*.*?\*\*)")


def make_run(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    font: str = "Times New Roman",
    size_half_pt: int = 28,
) -> ET.Element:
    """Build a w:r run with the given text and formatting.

    size_half_pt is the font size in half-points (28 == 14pt).
    """
    run = ET.Element(w_tag("r"))
    rpr = ET.SubElement(run, w_tag("rPr"))
    fonts = ET.SubElement(rpr, w_tag("rFonts"))
    for attr in ("ascii", "hAnsi", "cs"):
        fonts.set(w_tag(attr), font)
    ET.SubElement(rpr, w_tag("sz")).set(w_tag("val"), str(size_half_pt))
    ET.SubElement(rpr, w_tag("szCs")).set(w_tag("val"), str(size_half_pt))
    if bold:
        ET.SubElement(rpr, w_tag("b"))
    if italic:
        ET.SubElement(rpr, w_tag("i"))
    text_el = ET.SubElement(run, w_tag("t"))
    text_el.set(XML_SPACE, "preserve")
    text_el.text = text
    return run


def make_paragraph(
    style_id: str,
    runs: list[ET.Element] | None = None,
    *,
    page_break: bool = False,
    center: bool = False,
    align: str | None = None,
    ind_left: int | None = None,
    ind_first_line: int | None = None,
) -> ET.Element:
    """Build a w:p paragraph with the given style and optional alignment.

    ``ind_left`` / ``ind_first_line`` (twips) override any indent inherited
    from the style or computed from ``center``/``align``.
    """
    p = ET.Element(w_tag("p"))
    ppr = ET.SubElement(p, w_tag("pPr"))
    ET.SubElement(ppr, w_tag("pStyle")).set(w_tag("val"), style_id)

    explicit_ind = ind_left is not None or ind_first_line is not None

    if style_id in _HEADING_STYLES:
        # Disable inherited auto-numbering and override the hanging indent
        # so heading numbers are stable text we control, not list markers.
        numpr = ET.SubElement(ppr, w_tag("numPr"))
        ET.SubElement(numpr, w_tag("ilvl")).set(w_tag("val"), "0")
        ET.SubElement(numpr, w_tag("numId")).set(w_tag("val"), "0")
        if not explicit_ind:
            ind = ET.SubElement(ppr, w_tag("ind"))
            ind.set(w_tag("left"), "0")
            ind.set(w_tag("firstLine"), "0" if center else "720")

    if page_break:
        ET.SubElement(ppr, w_tag("pageBreakBefore"))

    effective_align = align if align is not None else ("center" if center else None)
    if effective_align is not None:
        ET.SubElement(ppr, w_tag("jc")).set(w_tag("val"), effective_align)

    if explicit_ind:
        ind = ET.SubElement(ppr, w_tag("ind"))
        ind.set(w_tag("left"), str(ind_left if ind_left is not None else 0))
        ind.set(w_tag("firstLine"), str(ind_first_line if ind_first_line is not None else 0))
    elif (
        style_id not in _HEADING_STYLES
        and (center or align in ("center", "left"))
    ):
        ind = ET.SubElement(ppr, w_tag("ind"))
        ind.set(w_tag("left"), "0")
        ind.set(w_tag("firstLine"), "0")

    for run in runs or ():
        p.append(run)
    return p


def make_empty_paragraph() -> ET.Element:
    return ET.Element(w_tag("p"))


def parse_inline(text: str) -> list[ET.Element]:
    """Split text on **bold** markers and return a list of runs."""
    runs: list[ET.Element] = []
    for part in _BOLD_PATTERN.split(text):
        if part.startswith("**") and part.endswith("**"):
            runs.append(make_run(part[2:-2], bold=True))
        elif part:
            runs.append(make_run(part))
    return runs
