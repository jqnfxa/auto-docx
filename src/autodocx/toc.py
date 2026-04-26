"""Build a Table of Contents structured-document tag."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from autodocx.ns import XML_SPACE, w_tag


def build_toc_sdt(
    *,
    style: str = "TOC1",
    levels: str = "1-4",
    placeholder: str = "Update the table of contents (Ctrl+A, F9)",
) -> ET.Element:
    """Return a w:sdt element holding a TOC field.

    Word/LibreOffice update the field on Ctrl+A → F9 and produce a real
    table of contents based on the document's heading paragraphs.
    """
    sdt = ET.Element(w_tag("sdt"))

    sdtpr = ET.SubElement(sdt, w_tag("sdtPr"))
    docpart = ET.SubElement(sdtpr, w_tag("docPartObj"))
    ET.SubElement(docpart, w_tag("docPartGallery")).set(w_tag("val"), "Table of Contents")

    sdtcontent = ET.SubElement(sdt, w_tag("sdtContent"))
    p = ET.SubElement(sdtcontent, w_tag("p"))
    ppr = ET.SubElement(p, w_tag("pPr"))
    ET.SubElement(ppr, w_tag("pStyle")).set(w_tag("val"), style)

    _field(p, "begin")
    instr_run = ET.SubElement(p, w_tag("r"))
    instr = ET.SubElement(instr_run, w_tag("instrText"))
    instr.set(XML_SPACE, "preserve")
    instr.text = f' TOC \\o "{levels}" \\h '
    _field(p, "separate")

    placeholder_run = ET.SubElement(p, w_tag("r"))
    ET.SubElement(placeholder_run, w_tag("t")).text = placeholder
    _field(p, "end")

    return sdt


def _field(parent: ET.Element, kind: str) -> None:
    run = ET.SubElement(parent, w_tag("r"))
    fld = ET.SubElement(run, w_tag("fldChar"))
    fld.set(w_tag("fldCharType"), kind)
