"""Convert markdown text containing LaTeX math to OOXML by shelling out to pandoc.

Pandoc converts ``$x$`` / ``$$x$$`` blocks into native ``m:oMath`` elements
inside a throwaway .docx, which we unzip and graft into our own document.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from autodocx.ns import M, w_tag

_RE_INLINE_MATH = re.compile(r"\$.*?\$")
_PANDOC_TIMEOUT_S = 10


class PandocUnavailable(RuntimeError):
    """Raised when pandoc is required but not on PATH."""


def has_math(text: str) -> bool:
    """Return True if text contains at least one ``$...$`` math span."""
    return bool(_RE_INLINE_MATH.search(text))


def is_display_math(text: str) -> bool:
    """Return True if text is a standalone ``$$...$$`` display formula."""
    s = text.strip()
    return s.startswith("$$") and s.endswith("$$")


def pandoc_md_to_omml(md_text: str) -> list[ET.Element] | None:
    """Convert a markdown snippet into a list of w:p elements with embedded m:oMath.

    Returns ``None`` on pandoc failure so the caller can fall back to plain text.
    """
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        try:
            proc = subprocess.run(
                ["pandoc", "-f", "markdown", "-t", "docx", "-o", tmp_path],
                input=md_text.encode("utf-8"),
                capture_output=True,
                timeout=_PANDOC_TIMEOUT_S,
            )
        except FileNotFoundError as exc:
            raise PandocUnavailable(
                "pandoc not found on PATH; install it to render LaTeX math"
            ) from exc

        if proc.returncode != 0:
            print(f"  pandoc error: {proc.stderr.decode(errors='replace')[:200]}")
            return None

        with zipfile.ZipFile(tmp_path) as z, z.open("word/document.xml") as f:
            doc_xml = f.read().decode()
    finally:
        os.unlink(tmp_path)

    body = ET.fromstring(doc_xml).find(w_tag("body"))
    if body is None:
        return None
    return [child for child in body if child.tag == w_tag("p")]


class FormulaConverter:
    """Cache pandoc invocations so repeated formulas only convert once."""

    def __init__(self) -> None:
        self._cache: dict[str, list[ET.Element] | None] = {}

    @staticmethod
    def has_math(text: str) -> bool:
        return has_math(text)

    @staticmethod
    def is_display_math(text: str) -> bool:
        return is_display_math(text)

    def convert_paragraph(
        self,
        text: str,
        *,
        style_id: str = "BodyText",
    ) -> list[ET.Element] | None:
        cached = self._cache.get(text)
        if cached is not None or text in self._cache:
            return cached

        paragraphs = pandoc_md_to_omml(text)
        if paragraphs is None:
            self._cache[text] = None
            return None

        for p in paragraphs:
            ppr = p.find(w_tag("pPr"))
            if ppr is None:
                ppr = ET.SubElement(p, w_tag("pPr"))
                p.insert(0, ppr)
            ps = ppr.find(w_tag("pStyle"))
            if ps is None:
                ps = ET.SubElement(ppr, w_tag("pStyle"))
            ps.set(w_tag("val"), style_id)

        self._cache[text] = paragraphs
        return paragraphs


__all__ = [
    "FormulaConverter",
    "PandocUnavailable",
    "has_math",
    "is_display_math",
    "pandoc_md_to_omml",
    "M",
]
