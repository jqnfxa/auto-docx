import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from autodocx.config import BuildConfig
from autodocx.ns import w_tag
from autodocx.pipeline import build_document

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPPED_TEMPLATE = REPO_ROOT / "docx" / "template.docx"


def _read_document_xml(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        return z.read("word/document.xml").decode()


def _heading_texts(doc_xml: str) -> list[tuple[str, str]]:
    """Return [(style, text), …] for each Heading2/3/4 paragraph."""
    root = ET.fromstring(doc_xml)
    body = root.find(w_tag("body"))
    out: list[tuple[str, str]] = []
    for p in body.findall(w_tag("p")):
        ppr = p.find(w_tag("pPr"))
        if ppr is None:
            continue
        ps = ppr.find(w_tag("pStyle"))
        if ps is None:
            continue
        style = ps.get(w_tag("val"), "")
        if not style.startswith("Heading"):
            continue
        text = "".join(t.text or "" for t in p.findall(f".//{w_tag('t')}"))
        out.append((style, text))
    return out


@pytest.mark.skipif(not SHIPPED_TEMPLATE.exists(), reason="docx/template.docx missing")
def test_shipped_sample_builds_end_to_end(tmp_path):
    """Build the in-tree autodocx.toml sample and inspect headings + TOC."""
    toml_path = REPO_ROOT / "autodocx.toml"
    config = BuildConfig.from_toml(toml_path)
    config.output = tmp_path / "out.docx"

    out = build_document(config)

    assert out == config.output
    assert out.exists()
    assert out.stat().st_size > 0

    doc_xml = _read_document_xml(out)
    assert "TOC " in doc_xml  # auto-update TOC field

    headings = _heading_texts(doc_xml)
    heading_text = [t for _, t in headings]
    assert "1 Первая глава (заголовок второго уровня)" in heading_text
    assert "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ" in heading_text
    assert "ПРИЛОЖЕНИЕ А (заголовок второго уровня)" in heading_text

    # References must come before the appendix when the marker is wired up.
    refs_idx = heading_text.index("СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ")
    appendix_idx = heading_text.index("ПРИЛОЖЕНИЕ А (заголовок второго уровня)")
    assert refs_idx < appendix_idx


def _write_minimal_template(path: Path) -> None:
    """Create a tiny but valid .docx that build_document can splice into."""
    body = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:sectPr/></w:body></w:document>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    )
    rels_ct = "application/vnd.openxmlformats-package.relationships+xml"
    doc_ct = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml"
        ".document.main+xml"
    )
    ct = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        f'<Default Extension="rels" ContentType="{rels_ct}"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/word/document.xml" ContentType="{doc_ct}"/>'
        "</Types>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", body)
        z.writestr("word/_rels/document.xml.rels", rels)


def test_stats_template_substitution(tmp_path):
    """{{n_pages}}/{{n_figures}}/{{n_tables}}/{{n_sources}} expand before parsing."""
    template = tmp_path / "template.docx"
    _write_minimal_template(template)

    md = tmp_path / "doc.md"
    md.write_text(
        "# Stats\n\n"
        "p={{n_pages}} f={{n_figures}} t={{n_tables}} s={{n_sources}}\n",
        encoding="utf-8",
    )

    out = tmp_path / "out.docx"
    config = BuildConfig(
        inputs=[md],
        template=template,
        output=out,
        manual_pages=42,
    )
    build_document(config)

    text = "".join(_read_document_xml(out).split())
    assert "p=42" in text
    assert "f=0t=0s=0" in text


def test_warning_when_citations_have_no_marker(tmp_path, capsys):
    """If markdown cites entries but no <!-- references --> marker exists, warn."""
    template = tmp_path / "template.docx"
    _write_minimal_template(template)

    bib = tmp_path / "refs.bib"
    bib.write_text("@online{a, title = {Alpha}}\n", encoding="utf-8")

    md = tmp_path / "doc.md"
    md.write_text("Citing [@a] without rendering the list.\n", encoding="utf-8")

    config = BuildConfig(
        inputs=[md],
        template=template,
        bibliography=bib,
        output=tmp_path / "out.docx",
    )
    build_document(config)

    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "<!-- references -->" in out


def test_marker_renders_references_inline(tmp_path):
    """When a marker is present, the bibliography entries land at the marker."""
    template = tmp_path / "template.docx"
    _write_minimal_template(template)

    bib = tmp_path / "refs.bib"
    bib.write_text("@online{a, title = {Alpha}}\n", encoding="utf-8")

    md = tmp_path / "doc.md"
    md.write_text("Cite [@a].\n\n<!-- references -->\n", encoding="utf-8")

    config = BuildConfig(
        inputs=[md],
        template=template,
        bibliography=bib,
        output=tmp_path / "out.docx",
    )
    build_document(config)

    doc = _read_document_xml(config.output)
    # Whitespace gets normalized when ET re-serializes; check the joined form.
    assert "1.Alpha." in "".join(doc.split())
