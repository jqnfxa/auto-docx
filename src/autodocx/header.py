"""Extract body and assets from a header.docx for prepending to the output."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from autodocx.ns import CT, RELS, w_tag


@dataclass
class HeaderAssets:
    elements: list[ET.Element] = field(default_factory=list)
    rels: dict[str, dict[str, str]] = field(default_factory=dict)
    media: dict[str, bytes] = field(default_factory=dict)
    extra_parts: dict[str, bytes] = field(default_factory=dict)
    ct_overrides: dict[str, str] = field(default_factory=dict)


# Parts whose content is supplied by the main template — copying them from
# the header would conflict with the template's styles, numbering, etc.
_SKIP_PARTS = frozenset({
    "word/document.xml",
    "word/styles.xml",
    "word/numbering.xml",
    "word/settings.xml",
    "word/fontTable.xml",
    "word/webSettings.xml",
    "word/_rels/document.xml.rels",
})


def extract_header_body(header_path: Path) -> HeaderAssets:
    """Open a .docx and pull out body content + dependent parts.

    Returned elements skip the trailing sectPr so they can be inlined at
    the start of another document's body. Relationships, media, and any
    other word/ parts (footers, comments, footnotes, custom XML) are
    forwarded so references inside the elements still resolve.
    """
    if not header_path.exists():
        print(f"  WARNING: Header file not found: {header_path}")
        return HeaderAssets()

    with zipfile.ZipFile(header_path, "r") as z:
        doc_xml = z.read("word/document.xml")
        rels_xml = _try_read(z, "word/_rels/document.xml.rels")
        ct_xml = _try_read(z, "[Content_Types].xml")
        media: dict[str, bytes] = {}
        extras: dict[str, bytes] = {}
        for name in z.namelist():
            if name in _SKIP_PARTS:
                continue
            if name.startswith("word/theme/") or name.startswith("docProps/"):
                continue
            if name.startswith("_rels/") or name == "[Content_Types].xml":
                continue
            if name.startswith("word/media/"):
                media[name] = z.read(name)
            elif name.startswith("word/") or name.startswith("customXml/"):
                extras[name] = z.read(name)

    elements: list[ET.Element] = []
    body = ET.fromstring(doc_xml).find(w_tag("body"))
    if body is not None:
        for child in body:
            if child.tag != w_tag("sectPr"):
                elements.append(child)

    rels: dict[str, dict[str, str]] = {}
    if rels_xml is not None:
        for rel in ET.fromstring(rels_xml).findall(f"{{{RELS}}}Relationship"):
            rels[rel.get("Id", "")] = {
                "Type": rel.get("Type", ""),
                "Target": rel.get("Target", ""),
            }

    ct_overrides: dict[str, str] = {}
    if ct_xml is not None:
        for ov in ET.fromstring(ct_xml).findall(f"{{{CT}}}Override"):
            part = ov.get("PartName", "").lstrip("/")
            ct_overrides[part] = ov.get("ContentType", "")

    return HeaderAssets(
        elements=elements,
        rels=rels,
        media=media,
        extra_parts=extras,
        ct_overrides=ct_overrides,
    )


def _try_read(z: zipfile.ZipFile, name: str) -> bytes | None:
    try:
        return z.read(name)
    except KeyError:
        return None
