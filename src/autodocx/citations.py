"""Resolve [@key] citations against a BibTeX-flavored .bib file."""

from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path

_RE_ENTRY = re.compile(r"@(\w+)\{(\w+),\s*(.*?)\n\}", re.DOTALL)
_RE_FIELD = re.compile(r'(\w+)\s*=\s*(?:\{(.+?)\}|"(.+?)"|(\w+))', re.DOTALL)
_RE_CITE_GROUP = re.compile(r"\[@([\w;@\s,\.]+?)\]")
_RE_CITE_KEY = re.compile(r"(\w+)(.*)")


class CitationResolver:
    """Two-pass citation handling.

    Pass 1: ``collect_citations`` scans every input file and assigns each
    unique key the next available number in order of first appearance.

    Pass 2: ``resolve_citations`` rewrites ``[@key]`` to ``[N]`` and
    ``[@key, p. M]`` to ``[N, с. M]`` (Russian by default; configurable).

    ``get_reference_list`` returns the ordered (number, formatted) pairs
    used to render the references section.
    """

    def __init__(
        self,
        bib_path: str | Path | None,
        *,
        page_label: str = "с.",
    ) -> None:
        self.page_label = page_label
        self.bib_entries: dict[str, str] = (
            _parse_bib(Path(bib_path)) if bib_path else {}
        )
        self.cited_keys: OrderedDict[str, int] = OrderedDict()

    def collect_citations(self, text: str) -> None:
        for m in _RE_CITE_GROUP.finditer(text):
            for ref in _split_refs(m.group(1)):
                key = _RE_CITE_KEY.match(ref)
                if key:
                    k = key.group(1)
                    if k not in self.cited_keys:
                        self.cited_keys[k] = len(self.cited_keys) + 1

    def resolve_citations(self, text: str) -> str:
        return _RE_CITE_GROUP.sub(self._replace_cite, text)

    def _replace_cite(self, m: re.Match[str]) -> str:
        parts: list[str] = []
        for ref in _split_refs(m.group(1)):
            km = _RE_CITE_KEY.match(ref)
            if not km:
                parts.append(ref)
                continue
            key = km.group(1)
            extra = km.group(2).strip()
            num = self.cited_keys.get(key, "?")
            if extra:
                extra = re.sub(r",\s*p\.\s*", f", {self.page_label} ", extra)
                extra = re.sub(r",\s*с\.\s*", f", {self.page_label} ", extra)
                parts.append(f"{num}{extra}")
            else:
                parts.append(str(num))
        return "[" + ", ".join(parts) + "]"

    def get_reference_list(self) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        for key, num in self.cited_keys.items():
            ref = self.bib_entries.get(key, f"[{key}] — entry missing from .bib")
            out.append((num, ref))
        return out


def _split_refs(group: str) -> list[str]:
    return [r.strip().lstrip("@") for r in re.split(r"\s*;\s*", group)]


def _parse_bib(path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8")
    entries: dict[str, str] = {}
    for m in _RE_ENTRY.finditer(content):
        entry_type = m.group(1)
        key = m.group(2)
        body = m.group(3)
        fields: dict[str, str] = {}
        for fm in _RE_FIELD.finditer(body):
            fname = fm.group(1)
            fval = fm.group(2) or fm.group(3) or fm.group(4) or ""
            fields[fname] = re.sub(r"[\{\}]", "", fval).strip()
        entries[key] = _format_entry(entry_type, fields)
    return entries


def _format_entry(entry_type: str, f: dict[str, str]) -> str:
    """Format a bib entry as a GOST-flavored reference string.

    Covers the subset of types the original pipeline produced
    (book / article / online / manual). Falls back to a generic
    ``Author. Title. Year`` form for anything else.
    """
    author = f.get("author", "")
    title = f.get("title", "")
    year = f.get("year", "")
    publisher = f.get("publisher", "")
    journal = f.get("journal", "")
    volume = f.get("volume", "")
    pages = f.get("pages", "")
    url = f.get("url", "")
    pagetotal = f.get("pagetotal", "")

    if entry_type == "book":
        out = f"{author}. {title}"
        if publisher:
            out += f" — {publisher}"
        if year:
            out += f", {year}"
        if pagetotal:
            out += f". — {pagetotal} с."
        return out

    if entry_type == "article":
        out = f"{author}. {title}"
        if journal:
            out += f" // {journal}"
        if volume:
            out += f". — Vol. {volume}"
        if year:
            out += f", {year}"
        if pages:
            out += f". — P. {pages}"
        return out

    if entry_type == "online":
        out = title
        if url:
            out += f" [Электронный ресурс]. URL: {url}"
        return out

    if entry_type == "manual":
        out = title
        if publisher:
            out += f". — {publisher}"
        if year:
            out += f", {year}"
        return out

    return f"{author}. {title}. {year}".strip(". ")
