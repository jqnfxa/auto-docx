"""End-to-end build: parse markdown, inject into template, write .docx."""

from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from autodocx.citations import CitationResolver
from autodocx.config import BuildConfig
from autodocx.formulas import FormulaConverter
from autodocx.header import HeaderAssets, extract_header_body
from autodocx.ns import CT, R_IMG, RELS, w_tag
from autodocx.parser import parse_md_text
from autodocx.renderer import RenderContext, render_blocks
from autodocx.runs import make_paragraph, make_run

_STATS_VARS = ("n_pages", "n_figures", "n_tables", "n_sources")
_RE_FIGURE_LINE = re.compile(r"^!\[", re.MULTILINE)


def build_document(config: BuildConfig) -> Path:
    """Build a .docx from the inputs described by ``config`` and return its path."""
    _validate_inputs(config)

    raw_sources = [(p, p.read_text(encoding="utf-8")) for p in config.inputs]

    citer = CitationResolver(config.bibliography) if config.bibliography else None
    if citer is not None:
        for _, text in raw_sources:
            citer.collect_citations(text)
        print(f"Citations found: {len(citer.cited_keys)} unique references")

    table_caption_re = re.compile(
        rf"^[ \t]*{re.escape(config.table_label)}\b", re.MULTILINE
    )
    n_figures = sum(len(_RE_FIGURE_LINE.findall(t)) for _, t in raw_sources)
    n_tables = sum(len(table_caption_re.findall(t)) for _, t in raw_sources)
    n_sources = len(citer.cited_keys) if citer else 0
    n_pages = config.manual_pages if config.manual_pages is not None else 0
    print(
        f"Counts: figures={n_figures}, tables={n_tables}, "
        f"sources={n_sources}, pages={n_pages or '(unset)'}"
    )

    sources = [(p, _substitute_stats(t, n_pages, n_figures, n_tables, n_sources))
               for p, t in raw_sources]

    formulas = FormulaConverter()
    ctx = RenderContext(
        pictures_dir=config.pictures_dir,
        citer=citer,
        formulas=formulas,
        title_pages=config.title_page_set,
        centered_headings=config.centered_heading_set,
        toc_heading=config.toc_heading,
        figure_label=config.figure_label,
    )

    body_elements = _render_all_inputs(sources, ctx, config)

    if citer is not None and citer.cited_keys:
        body_elements.extend(_build_references_section(citer, config))

    header_assets = (
        extract_header_body(config.header) if config.header else HeaderAssets()
    )
    if header_assets.elements:
        print(f"Header content: {len(header_assets.elements)} elements")
        _ensure_page_break_before(body_elements)

    _write_output(
        template=config.template,
        output=config.output,
        elements=header_assets.elements + body_elements,
        header=header_assets,
        registry=ctx.images,
    )

    print(f"Built: {config.output}")
    print("NOTE: Open in Word/LibreOffice and press Ctrl+A then F9 to refresh TOC and page numbers.")
    return config.output


# ---------------------------------------------------------------------------
# Input parsing & rendering


def _validate_inputs(config: BuildConfig) -> None:
    missing: list[Path] = []
    if not config.template.exists():
        missing.append(config.template)
    for p in config.inputs:
        if not p.exists():
            missing.append(p)
    if config.header and not config.header.exists():
        missing.append(config.header)
    if config.bibliography and not config.bibliography.exists():
        missing.append(config.bibliography)
    if missing:
        listing = "\n  ".join(str(p) for p in missing)
        raise FileNotFoundError(f"Missing inputs:\n  {listing}")


def _substitute_stats(
    text: str, n_pages: int, n_figures: int, n_tables: int, n_sources: int
) -> str:
    values = {
        "n_pages": n_pages,
        "n_figures": n_figures,
        "n_tables": n_tables,
        "n_sources": n_sources,
    }
    for var in _STATS_VARS:
        text = text.replace("{{" + var + "}}", str(values[var]))
    return text


def _render_all_inputs(
    sources: list[tuple[Path, str]],
    ctx: RenderContext,
    config: BuildConfig,
) -> list[ET.Element]:
    elements: list[ET.Element] = []
    for idx, (path, text) in enumerate(sources):
        blocks = parse_md_text(
            text,
            table_label=config.table_label,
            figure_label=config.figure_label,
        )
        is_first_file = idx == 0
        rendered = render_blocks(
            blocks,
            ctx,
            page_break_first_heading=not is_first_file,
            page_break_each_heading=True,
        )
        elements.extend(rendered)
    return elements


def _build_references_section(
    citer: CitationResolver, config: BuildConfig
) -> list[ET.Element]:
    label = config.references_heading or config.references_label
    out: list[ET.Element] = [
        make_paragraph(
            "Heading2",
            [make_run(label, bold=True)],
            page_break=True,
            center=True,
        )
    ]
    for num, ref_text in citer.get_reference_list():
        out.append(make_paragraph("BodyText", [make_run(f"{num}. {ref_text}")]))
    return out


def _ensure_page_break_before(elements: list[ET.Element]) -> None:
    """Force a page break before the first paragraph element."""
    if not elements:
        return
    first = elements[0]
    if first.tag != w_tag("p"):
        return
    ppr = first.find(w_tag("pPr"))
    if ppr is None:
        ppr = ET.Element(w_tag("pPr"))
        first.insert(0, ppr)
    if ppr.find(w_tag("pageBreakBefore")) is None:
        ET.SubElement(ppr, w_tag("pageBreakBefore"))


# ---------------------------------------------------------------------------
# Template injection (zip surgery on the .docx package)


def _write_output(
    *,
    template: Path,
    output: Path,
    elements: list[ET.Element],
    header: HeaderAssets,
    registry,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template, output)

    with zipfile.ZipFile(output, "r") as zin:
        doc_xml = zin.read("word/document.xml")
        rels_xml = zin.read("word/_rels/document.xml.rels")

    new_doc_xml = _splice_body(doc_xml, elements)
    new_rels_xml = _extend_rels(rels_xml, registry, header)

    if header.elements:
        _rewrite_header_rids(header.elements, header.rels)

    with zipfile.ZipFile(output, "r") as zin:
        contents = {
            name: zin.read(name)
            for name in zin.namelist()
            if name not in ("word/document.xml", "word/_rels/document.xml.rels")
        }

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in contents.items():
            zout.writestr(name, data)
        zout.writestr("word/document.xml", new_doc_xml)
        zout.writestr("word/_rels/document.xml.rels", new_rels_xml)
        for media_path, media_data in header.media.items():
            if media_path not in contents:
                zout.writestr(media_path, media_data)
        for part_path, part_data in header.extra_parts.items():
            if part_path not in contents:
                zout.writestr(part_path, part_data)
        for entry in registry.items():
            if entry.abs_path.exists():
                zout.write(entry.abs_path, f"word/media/{entry.media_name}")

    _update_content_types(output, header.ct_overrides)


def _splice_body(doc_xml: bytes, elements: list[ET.Element]) -> str:
    root = ET.fromstring(doc_xml)
    body = root.find(w_tag("body"))
    if body is None:
        raise RuntimeError("Template document.xml has no w:body element")

    for child in list(body):
        if child.tag != w_tag("sectPr"):
            body.remove(child)
    for idx, el in enumerate(elements):
        body.insert(idx, el)
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def _extend_rels(rels_xml: bytes, registry, header: HeaderAssets) -> str:
    rels_root = ET.fromstring(rels_xml)
    ET.register_namespace("", RELS)

    for entry in registry.items():
        rel = ET.SubElement(rels_root, "Relationship")
        rel.set("Id", entry.rid)
        rel.set("Type", R_IMG)
        rel.set("Target", f"media/{entry.media_name}")

    for old_rid, info in header.rels.items():
        rel = ET.SubElement(rels_root, "Relationship")
        rel.set("Id", _prefix_rid(old_rid))
        rel.set("Type", info.get("Type", ""))
        rel.set("Target", info.get("Target", ""))

    return ET.tostring(rels_root, encoding="unicode", xml_declaration=True)


def _rewrite_header_rids(
    elements: list[ET.Element], header_rels: dict[str, dict[str, str]]
) -> None:
    """Rewrite r:embed/r:id/r:link in header elements to the prefixed rids."""
    if not header_rels:
        return
    rid_map = {old: _prefix_rid(old) for old in header_rels}
    r_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    targets = (f"{{{r_ns}}}embed", f"{{{r_ns}}}id", f"{{{r_ns}}}link")
    for el in elements:
        for sub in el.iter():
            for attr in targets:
                if attr in sub.attrib and sub.attrib[attr] in rid_map:
                    sub.attrib[attr] = rid_map[sub.attrib[attr]]


def _prefix_rid(rid: str) -> str:
    return f"hdr{rid}"


def _update_content_types(docx_path: Path, header_overrides: dict[str, str]) -> None:
    """Ensure png/jpg defaults exist and forward header overrides."""
    with zipfile.ZipFile(docx_path, "r") as zin:
        ct_xml = zin.read("[Content_Types].xml")
        contents = {
            name: zin.read(name)
            for name in zin.namelist()
            if name != "[Content_Types].xml"
        }

    ET.register_namespace("", CT)
    root = ET.fromstring(ct_xml)

    existing_exts = {
        d.get("Extension", "").lower() for d in root.findall(f"{{{CT}}}Default")
    }
    for ext, mime in (("png", "image/png"), ("jpg", "image/jpeg"), ("jpeg", "image/jpeg")):
        if ext not in existing_exts:
            d = ET.SubElement(root, f"{{{CT}}}Default")
            d.set("Extension", ext)
            d.set("ContentType", mime)

    if header_overrides:
        existing = {
            ov.get("PartName", "").lstrip("/")
            for ov in root.findall(f"{{{CT}}}Override")
        }
        for part_name, ct in header_overrides.items():
            if part_name in contents and part_name not in existing:
                ov = ET.SubElement(root, f"{{{CT}}}Override")
                ov.set("PartName", "/" + part_name)
                ov.set("ContentType", ct)

    new_xml = ET.tostring(root, encoding="unicode", xml_declaration=True)
    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in contents.items():
            zout.writestr(name, data)
        zout.writestr("[Content_Types].xml", new_xml)


__all__ = ["build_document"]
