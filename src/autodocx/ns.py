"""OOXML namespaces and tag helpers."""

import xml.etree.ElementTree as ET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
R_IMG = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"

CT = "http://schemas.openxmlformats.org/package/2006/content-types"
RELS = "http://schemas.openxmlformats.org/package/2006/relationships"

XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

_REGISTERED = False


def register_namespaces() -> None:
    """Register OOXML namespaces with ElementTree (idempotent)."""
    global _REGISTERED
    if _REGISTERED:
        return
    ET.register_namespace("w", W)
    ET.register_namespace("r", R)
    ET.register_namespace("m", M)
    ET.register_namespace("wp", WP)
    ET.register_namespace("a", A)
    ET.register_namespace("pic", PIC)
    ET.register_namespace("w14", "http://schemas.microsoft.com/office/word/2010/wordml")
    ET.register_namespace("w15", "http://schemas.microsoft.com/office/word/2012/wordml")
    ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")
    ET.register_namespace("wps", "http://schemas.microsoft.com/office/word/2010/wordprocessingShape")
    ET.register_namespace("wpg", "http://schemas.microsoft.com/office/word/2010/wordprocessingGroup")
    _REGISTERED = True


register_namespaces()


def w_tag(name: str) -> str:
    return f"{{{W}}}{name}"


def m_tag(name: str) -> str:
    return f"{{{M}}}{name}"


def r_tag(name: str) -> str:
    return f"{{{R}}}{name}"
