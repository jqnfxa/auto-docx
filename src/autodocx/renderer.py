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
            elements.extend(_render_text("BodyText", data, ctx))
        elif kind == "bullet":
            elements.append(_render_bullet(data, ctx))
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
        result = ctx.formulas.convert_paragraph(text, style_id=style)
        if result:
            if align is not None:
                _apply_alignment(result, align)
            return list(result)
    return [make_paragraph(style, parse_inline(text), align=align)]


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


def _render_bullet(data: tuple[int, str], ctx: RenderContext) -> ET.Element:
    """Render a bullet item at the given nesting level.

    Each level adds 1.25 cm of left margin and rotates through ``•``/``○``/``▪``
    markers, matching the template's three-level bullet convention.
    """
    level, text = data
    marker = BULLET_MARKERS[level % len(BULLET_MARKERS)]
    indent = (level + 1) * BULLET_INDENT_PER_LEVEL_TWIPS
    body = parse_inline(f"{marker}  {_resolve(text, ctx)}")
    return make_paragraph(
        "BodyText",
        body,
        ind_left=indent,
        ind_first_line=0,
    )


def _render_image(data: tuple[str, str], ctx: RenderContext) -> list[ET.Element]:
    img_path, caption = data
    candidate = ctx.pictures_dir / img_path
    full_path = candidate if candidate.exists() else Path(img_path)
    elements = [make_image_paragraph(full_path, ctx.images)]
    cap_text = f"{ctx.figure_label} {ctx.fig_counter[0]} – {caption}"
    elements.extend(_render_text("Style15", cap_text, ctx, align="center"))
    ctx.fig_counter[0] += 1
    return elements
