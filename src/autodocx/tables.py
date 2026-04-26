"""Build w:tbl from markdown table syntax."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from autodocx.ns import w_tag
from autodocx.runs import make_run

# Table-cell style from the original VKR template; users can override if their
# template doesn't define it (cells will fall back to default formatting).
DEFAULT_CELL_STYLE = "Style13"
DEFAULT_TABLE_WIDTH = 9000  # twentieths of a point (~6.25 inches)


def _split_cells(line: str) -> list[str]:
    """Split a markdown table row, accepting both bordered and bare styles."""
    cells = line.split("|")
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def _make_cell_content(text: str, formulas=None, *, bold: bool = False) -> list[ET.Element]:
    """Build paragraph children for a cell, routing math through pandoc."""
    text = text.replace("---", "—").replace("--", "—")
    if formulas is not None and formulas.has_math(text):
        result = formulas.convert_paragraph(text, style_id=DEFAULT_CELL_STYLE)
        if result:
            children: list[ET.Element] = []
            for p in result:
                for child in list(p):
                    if child.tag != w_tag("pPr"):
                        children.append(child)
            return children
    return [make_run(text, bold=bold)]


def _add_borders(tpr: ET.Element) -> None:
    borders = ET.SubElement(tpr, w_tag("tblBorders"))
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = ET.SubElement(borders, w_tag(side))
        b.set(w_tag("val"), "single")
        b.set(w_tag("sz"), "4")
        b.set(w_tag("space"), "0")
        b.set(w_tag("color"), "000000")


def _build_cell(text: str, formulas, *, align: str, bold: bool) -> ET.Element:
    tc = ET.Element(w_tag("tc"))
    p = ET.SubElement(tc, w_tag("p"))
    ppr = ET.SubElement(p, w_tag("pPr"))
    ET.SubElement(ppr, w_tag("pStyle")).set(w_tag("val"), DEFAULT_CELL_STYLE)
    ET.SubElement(ppr, w_tag("jc")).set(w_tag("val"), align)
    for child in _make_cell_content(text, formulas=formulas, bold=bold):
        p.append(child)
    return tc


def build_table(
    lines: list[str],
    formulas=None,
    *,
    table_width: int = DEFAULT_TABLE_WIDTH,
) -> ET.Element | None:
    """Build a w:tbl from a list of markdown table source lines.

    Expects standard pipe-table syntax: header row, separator row, then data.
    The header is marked with tblHeader so Word repeats it across pages.
    """
    if len(lines) < 3:
        return None

    header = _split_cells(lines[0])
    rows = [_split_cells(line) for line in lines[2:]]
    ncols = len(header)
    if ncols == 0:
        return None

    tbl = ET.Element(w_tag("tbl"))
    tpr = ET.SubElement(tbl, w_tag("tblPr"))
    tw = ET.SubElement(tpr, w_tag("tblW"))
    tw.set(w_tag("w"), "0")
    tw.set(w_tag("type"), "auto")
    _add_borders(tpr)

    grid = ET.SubElement(tbl, w_tag("tblGrid"))
    col_w = table_width // ncols
    for _ in range(ncols):
        ET.SubElement(grid, w_tag("gridCol")).set(w_tag("w"), str(col_w))

    # Header row — repeat across pages, never split.
    tr = ET.SubElement(tbl, w_tag("tr"))
    trpr = ET.SubElement(tr, w_tag("trPr"))
    ET.SubElement(trpr, w_tag("tblHeader"))
    ET.SubElement(trpr, w_tag("cantSplit"))
    for cell_text in header:
        tr.append(_build_cell(cell_text, formulas, align="center", bold=True))

    for row in rows:
        tr = ET.SubElement(tbl, w_tag("tr"))
        for idx, cell_text in enumerate(row):
            align = "left" if idx == 0 else "center"
            tr.append(_build_cell(cell_text, formulas, align=align, bold=False))

    return tbl
