"""Convert parsed markdown blocks into docx XML elements."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from autodocx.images import ImageRegistry, make_image_paragraph
from autodocx.ns import w_tag
from autodocx.runs import make_paragraph, make_run, parse_inline
from autodocx.tables import build_table
from autodocx.toc import build_toc_sdt

if TYPE_CHECKING:
    from autodocx.citations import CitationResolver
    from autodocx.formulas import FormulaConverter
    from autodocx.parser import Block

_RE_NUMBERED_ITEM = re.compile(r"^(\d+\.\s+)(.*)$", re.DOTALL)

# Numbered display math: `$$math$$ (N)` or `$$math$$ (N),` / `$$math$$ (N).`
# When matched, the formula is rendered centered via tab stops and the
# `(N)` floats to the right margin; the trailing punctuation (if any) is
# appended to the math content so it stays glued to the formula.
_RE_NUMBERED_DISPLAY_MATH = re.compile(
    r"^\s*\$\$(?P<math>.+?)\$\$\s*\((?P<num>\d+)\)(?P<punct>[.,;:]?)\s*$",
    re.DOTALL,
)

# Tab-stop positions for the centered-formula / right-aligned-number layout.
# A4 with the template's margins gives ~9072 twips of usable text width.
FORMULA_CENTER_TAB_TWIPS = 4536
FORMULA_RIGHT_TAB_TWIPS = 9072

# Per template: each list level adds 1.25 cm (≈ 709 twips) to the left indent.
BULLET_INDENT_PER_LEVEL_TWIPS = 709
BULLET_MARKERS = ("•", "○", "▪", "·")


@dataclass
class RenderContext:
    """Mutable rendering state shared across input files."""

    pictures_dir: Path
    images: ImageRegistry = field(default_factory=ImageRegistry)
    citer: CitationResolver | None = None
    formulas: FormulaConverter | None = None
    fig_counter: list[int] = field(default_factory=lambda: [1])
    title_pages: frozenset[str] = frozenset()
    centered_headings: frozenset[str] = frozenset()
    figure_label: str = "Рисунок"
    # Flipped to True the first time a `<!-- references -->` marker emits
    # the bibliography list, so the pipeline can detect "cited but not
    # rendered" and warn.
    references_rendered: bool = False
    # Set to True after a numbered display formula that ends with `,` or
    # `;` (i.e. continues the surrounding sentence). The next paragraph
    # consumes the flag and renders without its first-line indent — this
    # matches the Russian academic convention where the post-formula
    # "где: …" line is the continuation of the introducing sentence, not
    # a new thought.
    next_paragraph_no_first_indent: bool = False

    def is_title_page(self, heading: str) -> bool:
        return heading.strip() in self.title_pages

    def is_centered(self, heading: str) -> bool:
        h = heading.strip()
        return h in self.title_pages or h in self.centered_headings


def build_references_entries(citer: CitationResolver) -> list[ET.Element]:
    """Return one numbered ``BodyText`` paragraph per cited bib entry.

    No heading is emitted — the caller is expected to author its own
    section heading in markdown (e.g. ``# СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ``)
    immediately before the ``<!-- references -->`` marker.
    """
    return [
        make_paragraph("BodyText", [make_run(f"{num}. {ref_text}")])
        for num, ref_text in citer.get_reference_list()
    ]


def render_blocks(
    blocks: list[Block],
    ctx: RenderContext,
    *,
    page_break_first_heading: bool = False,
    page_break_each_heading: bool = True,
) -> list[ET.Element]:
    """Render blocks to XML elements.

    ``page_break_first_heading`` decides whether the *first* H2 in this batch
    gets a page break; subsequent H2s always do when ``page_break_each_heading``
    is True. This matches the original behavior where intro.md doesn't break
    on its first heading but each chapter file does.
    """
    elements: list[ET.Element] = []
    seen_h2 = False

    for kind, data in blocks:
        # The continuation flag is consumed by the very next block
        # regardless of kind, but only changes the visual indent when
        # that block is a paragraph. Anything else (bullet, heading,
        # table, image, …) breaks the continuation silently.
        suppress_first_indent = (
            ctx.next_paragraph_no_first_indent and kind == "paragraph"
        )
        ctx.next_paragraph_no_first_indent = False

        if kind == "heading2":
            page_break = (
                page_break_each_heading and (seen_h2 or page_break_first_heading)
            )
            seen_h2 = True
            elements.append(_render_heading2(data, ctx, page_break))
            continue

        if kind == "heading3":
            elements.append(make_paragraph("Heading3", [make_run(data, bold=True)]))
        elif kind == "heading4":
            elements.append(make_paragraph("Heading4", [make_run(data, bold=True)]))
        elif kind == "paragraph":
            para_elements = _render_text("BodyText", data, ctx)
            if suppress_first_indent:
                for el in para_elements:
                    _suppress_first_line_indent(el)
            elements.extend(para_elements)
        elif kind == "bullet":
            elements.extend(_render_bullet(data, ctx))
        elif kind == "list_item":
            elements.extend(_render_list_item(data, ctx))
        elif kind == "table_caption":
            elements.extend(_render_text("Style14", data, ctx, align="left"))
        elif kind == "continuation_caption":
            elements.append(
                make_paragraph(
                    "Style14",
                    [make_run(_resolve(data, ctx))],
                    align="left",
                    page_break=True,
                )
            )
        elif kind == "figure_caption":
            elements.extend(_render_text("Style15", data, ctx, align="center"))
        elif kind == "table":
            tbl = build_table(data, ctx.formulas)
            if tbl is not None:
                elements.append(tbl)
        elif kind == "image":
            elements.extend(_render_image(data, ctx))
        elif kind == "toc_marker":
            elements.append(build_toc_sdt())
        elif (
            kind == "references_marker"
            and not ctx.references_rendered
            and ctx.citer is not None
            and ctx.citer.cited_keys
        ):
            elements.extend(build_references_entries(ctx.citer))
            ctx.references_rendered = True

    return elements


def _render_heading2(text: str, ctx: RenderContext, page_break: bool) -> ET.Element:
    if ctx.is_title_page(text):
        return make_paragraph(
            "BodyText",
            [make_run(text, bold=True)],
            page_break=page_break,
            center=True,
        )
    centered = ctx.is_centered(text)
    return make_paragraph(
        "Heading2",
        [make_run(text, bold=True)],
        page_break=page_break,
        center=centered,
    )


def _resolve(text: str, ctx: RenderContext) -> str:
    text = text.replace("---", "—").replace("--", "—")
    if ctx.citer is not None:
        text = ctx.citer.resolve_citations(text)
    return text


def _render_text(
    style: str,
    text: str,
    ctx: RenderContext,
    *,
    align: str | None = None,
) -> list[ET.Element]:
    """Render a single line of body text. Routes through pandoc when math is present."""
    text = _resolve(text, ctx)
    if ctx.formulas is not None and ctx.formulas.has_math(text):
        numbered = _try_render_numbered_display_math(style, text, ctx)
        if numbered is not None:
            return numbered
        result = ctx.formulas.convert_paragraph(text, style_id=style)
        if result:
            if align is not None:
                _apply_alignment(result, align)
            return list(result)
    return [make_paragraph(style, parse_inline(text), align=align)]


def _try_render_numbered_display_math(
    style: str,
    text: str,
    ctx: RenderContext,
) -> list[ET.Element] | None:
    """If ``text`` is ``$$math$$ (N)`` (optionally + ``,`` or ``.``), render it
    as a centered formula with the number right-aligned via tab stops.

    Returns ``None`` if the pattern doesn't match or pandoc fails.
    """
    m = _RE_NUMBERED_DISPLAY_MATH.match(text)
    if m is None or ctx.formulas is None:
        return None

    inner = m.group("math").strip()
    number = m.group("num")
    punct = m.group("punct")

    rendered = ctx.formulas.convert_paragraph(f"$${inner}$$", style_id=style)
    if not rendered:
        return None

    para = rendered[0]
    ppr = para.find(w_tag("pPr"))
    if ppr is None:
        ppr = ET.Element(w_tag("pPr"))
        para.insert(0, ppr)

    # Clear inherited centering (we'll center via tab stops instead) and any
    # existing first-line indent so the layout starts flush left.
    for jc in ppr.findall(w_tag("jc")):
        ppr.remove(jc)
    for ind in ppr.findall(w_tag("ind")):
        ppr.remove(ind)
    for tabs in ppr.findall(w_tag("tabs")):
        ppr.remove(tabs)
    ind = ET.SubElement(ppr, w_tag("ind"))
    ind.set(w_tag("left"), "0")
    ind.set(w_tag("firstLine"), "0")
    tabs = ET.SubElement(ppr, w_tag("tabs"))
    # Clear the BodyText style's inherited left tab at 709 twips, otherwise
    # the leading <w:tab/> jumps there instead of to our center tab.
    clear_tab = ET.SubElement(tabs, w_tag("tab"))
    clear_tab.set(w_tag("val"), "clear")
    clear_tab.set(w_tag("pos"), "709")
    center_tab = ET.SubElement(tabs, w_tag("tab"))
    center_tab.set(w_tag("val"), "center")
    center_tab.set(w_tag("pos"), str(FORMULA_CENTER_TAB_TWIPS))
    right_tab = ET.SubElement(tabs, w_tag("tab"))
    right_tab.set(w_tag("val"), "right")
    right_tab.set(w_tag("pos"), str(FORMULA_RIGHT_TAB_TWIPS))

    # Pandoc wraps display math in m:oMathPara, inline math in bare m:oMath.
    # Either is fine for us — we extract the inner m:oMath and insert it
    # directly into the paragraph so the paragraph's tab stops can apply.
    omath_para = next(
        (c for c in para if c.tag.endswith("}oMathPara")),
        None,
    )
    if omath_para is not None:
        omath = next(
            (c for c in omath_para if c.tag.endswith("}oMath")),
            None,
        )
    else:
        omath = next(
            (c for c in para if c.tag.endswith("}oMath")),
            None,
        )
    if omath is None:
        return None

    # Strip everything except pPr; we'll rebuild the post-math layout from
    # scratch.
    for c in list(para):
        if c is ppr:
            continue
        para.remove(c)

    tab_before = ET.Element(w_tag("r"))
    ET.SubElement(tab_before, w_tag("tab"))
    para.append(tab_before)
    para.append(omath)

    if punct:
        para.append(make_run(punct))

    tab_after = ET.Element(w_tag("r"))
    ET.SubElement(tab_after, w_tag("tab"))
    para.append(tab_after)
    para.append(make_run(f"({number})"))

    if punct in (",", ";"):
        ctx.next_paragraph_no_first_indent = True

    return [para]


def _suppress_first_line_indent(para: ET.Element) -> None:
    """Override a paragraph's first-line indent to 0 (flush-left start)."""
    if para.tag != w_tag("p"):
        return
    ppr = para.find(w_tag("pPr"))
    if ppr is None:
        ppr = ET.Element(w_tag("pPr"))
        para.insert(0, ppr)
    for existing in ppr.findall(w_tag("ind")):
        ppr.remove(existing)
    ind = ET.SubElement(ppr, w_tag("ind"))
    ind.set(w_tag("left"), "0")
    ind.set(w_tag("firstLine"), "0")


def _apply_alignment(paragraphs: list[ET.Element], align: str) -> None:
    for p in paragraphs:
        ppr = p.find(w_tag("pPr"))
        if ppr is None:
            ppr = ET.Element(w_tag("pPr"))
            p.insert(0, ppr)
        for jc in ppr.findall(w_tag("jc")):
            ppr.remove(jc)
        ET.SubElement(ppr, w_tag("jc")).set(w_tag("val"), align)


def _render_list_item(data: str, ctx: RenderContext) -> list[ET.Element]:
    """Numbered list items: keep the manual ``N. `` prefix as plain text.

    Pandoc would otherwise reinterpret ``N. text`` as a markdown ordered list
    and emit numbered paragraphs that depend on numbering.xml entries we
    don't ship with the template.
    """
    m = _RE_NUMBERED_ITEM.match(data)
    if not m:
        return _render_text("BodyText", data, ctx)

    prefix = m.group(1)
    rest = _resolve(m.group(2), ctx)

    if ctx.formulas is not None and ctx.formulas.has_math(rest):
        result = ctx.formulas.convert_paragraph(rest, style_id="BodyText")
        if result and result[0].tag == w_tag("p"):
            ppr = result[0].find(w_tag("pPr"))
            if ppr is not None:
                for npr in ppr.findall(w_tag("numPr")):
                    ppr.remove(npr)
            insert_idx = next(
                (
                    i
                    for i, c in enumerate(list(result[0]))
                    if c.tag != w_tag("pPr")
                ),
                len(list(result[0])),
            )
            result[0].insert(insert_idx, make_run(prefix))
            return list(result)

    return [make_paragraph("BodyText", parse_inline(prefix + rest))]


def _render_bullet(data: tuple[int, str], ctx: RenderContext) -> list[ET.Element]:
    """Render a bullet item at the given nesting level.

    Each level adds 1.25 cm of left margin and rotates through ``•``/``○``/``▪``
    markers, matching the template's three-level bullet convention.
    """
    level, text = data
    marker = BULLET_MARKERS[level % len(BULLET_MARKERS)]
    indent = (level + 1) * BULLET_INDENT_PER_LEVEL_TWIPS
    resolved = _resolve(text, ctx)

    if ctx.formulas is not None and ctx.formulas.has_math(resolved):
        result = ctx.formulas.convert_paragraph(resolved, style_id="BodyText")
        if result and result[0].tag == w_tag("p"):
            ppr = result[0].find(w_tag("pPr"))
            if ppr is None:
                ppr = ET.Element(w_tag("pPr"))
                result[0].insert(0, ppr)
            for npr in ppr.findall(w_tag("numPr")):
                ppr.remove(npr)
            for ind_existing in ppr.findall(w_tag("ind")):
                ppr.remove(ind_existing)
            ind = ET.SubElement(ppr, w_tag("ind"))
            ind.set(w_tag("left"), str(indent))
            ind.set(w_tag("firstLine"), "0")
            insert_idx = next(
                (i for i, c in enumerate(list(result[0])) if c.tag != w_tag("pPr")),
                len(list(result[0])),
            )
            result[0].insert(insert_idx, make_run(f"{marker}  "))
            return list(result)

    body = parse_inline(f"{marker}  {resolved}")
    return [make_paragraph(
        "BodyText",
        body,
        ind_left=indent,
        ind_first_line=0,
    )]


def _render_image(data: tuple[str, str], ctx: RenderContext) -> list[ET.Element]:
    img_path, caption = data
    candidate = ctx.pictures_dir / img_path
    full_path = candidate if candidate.exists() else Path(img_path)
    elements = [make_image_paragraph(full_path, ctx.images)]
    cap_text = f"{ctx.figure_label} {ctx.fig_counter[0]} – {caption}"
    elements.extend(_render_text("Style15", cap_text, ctx, align="center"))
    ctx.fig_counter[0] += 1
    return elements
