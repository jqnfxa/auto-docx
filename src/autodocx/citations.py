"""Resolve [@key] citations against a BibTeX-flavored .bib file."""

from __future__ import annotations

import re
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

_RE_ENTRY_HEADER = re.compile(r"@(\w+)\s*\{\s*(\w+)\s*,", re.DOTALL)
_RE_FIELD = re.compile(r'(\w+)\s*=\s*(?:\{(.+?)\}|"(.+?)"|(\w+))', re.DOTALL)
_RE_CITE_GROUP = re.compile(r"\[@([\w;@\s,\.]+?)\]")
_RE_CITE_KEY = re.compile(r"(\w+)(.*)")


def _iter_entries(content: str) -> Iterator[tuple[str, str, str]]:
    r"""Yield ``(entry_type, key, body)`` tuples by walking balanced braces.

    Handles both multi-line and single-line ``@type{key, …}`` entries by
    counting brace depth, so a single-line entry like ``@online{a, t = {x}}``
    parses just as cleanly as the indented multi-line shape.
    """
    pos = 0
    while True:
        m = _RE_ENTRY_HEADER.search(content, pos)
        if m is None:
            return
        depth = 1
        i = m.end()
        body_start = i
        while i < len(content) and depth > 0:
            ch = content[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1
        if depth != 0:
            return
        yield m.group(1), m.group(2), content[body_start : i - 1]
        pos = i


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
    for entry_type, key, body in _iter_entries(content):
        fields: dict[str, str] = {}
        for fm in _RE_FIELD.finditer(body):
            fname = fm.group(1)
            fval = fm.group(2) or fm.group(3) or fm.group(4) or ""
            fields[fname] = re.sub(r"[\{\}]", "", fval).strip()
        entries[key] = _format_entry(entry_type, fields)
    return entries


def _split_authors(author: str) -> list[str]:
    """Split a BibTeX ``author`` field on `` and `` into individual authors."""
    return [a.strip() for a in author.split(" and ") if a.strip()]


def _surname_first_list(author: str) -> str:
    """Render authors as ``Surname, Initials, Surname, Initials`` (GOST opener)."""
    return ", ".join(_split_authors(author))


def _initials_first_list(author: str) -> str:
    """Render authors as ``Initials Surname, Initials Surname`` (GOST after ``/``)."""
    out: list[str] = []
    for a in _split_authors(author):
        if "," in a:
            surname, initials = (p.strip() for p in a.split(",", 1))
            out.append(f"{initials} {surname}" if initials else surname)
        else:
            out.append(a)
    return ", ".join(out)


def _format_urldate(value: str) -> str:
    """Convert ``YYYY-MM-DD`` (or ``YYYY/MM/DD``) to ``DD.MM.YYYY``.

    Returns the input unchanged if it doesn't match the expected shape so
    pre-formatted dates pass through.
    """
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", value.strip())
    if not m:
        return value
    y, mo, d = m.groups()
    return f"{int(d):02d}.{int(mo):02d}.{y}"


def _format_entry(entry_type: str, f: dict[str, str]) -> str:
    """Format a bib entry as a GOST-flavored reference string.

    Supports book / article / online / manual; falls back to a generic
    ``Author. Title. Year`` form for anything else.
    """
    author = f.get("author", "")
    title = f.get("title", "")
    year = f.get("year", "")
    publisher = f.get("publisher", "")
    journal = f.get("journal", "")
    volume = f.get("volume", "")
    number = f.get("number", "")
    pages = f.get("pages", "")
    url = f.get("url", "")
    urldate = f.get("urldate", "")
    pagetotal = f.get("pagetotal", "")

    if entry_type == "book":
        out = f"{_surname_first_list(author)}. {title}" if author else title
        if publisher:
            out += f" — {publisher}"
        if year:
            out += f", {year}"
        if pagetotal:
            out += f". — {pagetotal} с."
        return out

    if entry_type == "article":
        # GOST: "Surname, Initials, Surname, Initials, Title /
        #        Initials Surname, Initials Surname //
        #        Journal. – Year. – № N. – С. pages."
        surnames = _surname_first_list(author)
        initials = _initials_first_list(author)
        out = f"{surnames}, {title}" if surnames else title
        if initials:
            out += f" / {initials}"
        if journal:
            out += f" // {journal}"
        if year:
            out += f". – {year}"
        if volume:
            out += f". – Т. {volume}"
        if number:
            out += f". – № {number}"
        if pages:
            out += f". – С. {pages}"
        return out + "."

    if entry_type == "online":
        out = title
        if url:
            out += f" [Электронный ресурс]. URL: {url}"
        if urldate:
            out += f" (дата обращения: {_format_urldate(urldate)})"
        return out + "."

    if entry_type == "manual":
        out = title
        if publisher:
            out += f". — {publisher}"
        if year:
            out += f", {year}"
        return out

    base = ". ".join(p for p in (_surname_first_list(author), title, year) if p)
    return base.strip(". ")
