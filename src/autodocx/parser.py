"""Parse a Markdown source file into a flat list of typed blocks.

Each block is a tuple ``(kind, data)`` consumed by :mod:`autodocx.renderer`:

- ``("heading2", text)`` / ``("heading3", text)``
- ``("paragraph", text)`` / ``("list_item", text)``
- ``("bullet", (level, text))`` — level is 0 for top-level, 1 for nested, …
- ``("table", lines)`` — raw markdown table lines (with or without outer pipes)
- ``("table_caption", text)`` / ``("continuation_caption", text)``
- ``("figure_caption", text)``
- ``("image", (path, caption))``
- ``("toc_marker", None)`` — emitted for ``<!-- toc -->``
- ``("references_marker", None)`` — emitted for ``<!-- references -->``
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

Block = tuple[str, Any]

_RE_HEADING2 = re.compile(r"^# (?!#)(.*)$")
_RE_HEADING3 = re.compile(r"^## (?!#)(.*)$")
_RE_HEADING4 = re.compile(r"^### (.*)$")
_RE_LIST_ITEM = re.compile(r"^(\d+)\.\s+(.*)$")
_RE_LIST_ITEM_PARAGRAPH_BREAKER = re.compile(r"^1\.\s+")
_RE_IMAGE = re.compile(r"^!\[(.*?)\]\(([^)]+)\)(?:\{[^}]*\})?\s*$")
_RE_CONTINUATION = re.compile(r"^продолжение таблицы\s", re.IGNORECASE)
_RE_BULLET = re.compile(r"^([ \t]*)[-*]\s+(.*)$")
_RE_TABLE_SEP_CELL = re.compile(r"^:?-{2,}:?$")

INDENT_SPACES_PER_LEVEL = 2

# Configurable label prefixes for figure/table captions. 
# Pass overrides via parse_md if needed.
DEFAULT_TABLE_LABEL = "Таблица"
DEFAULT_FIGURE_LABEL = "Рисунок"


def parse_md(
    filepath: str | Path,
    *,
    table_label: str = DEFAULT_TABLE_LABEL,
    figure_label: str = DEFAULT_FIGURE_LABEL,
) -> list[Block]:
    """Read a markdown file and return its blocks."""
    text = Path(filepath).read_text(encoding="utf-8")
    return parse_md_text(text, table_label=table_label, figure_label=figure_label)


def parse_md_text(
    text: str,
    *,
    table_label: str = DEFAULT_TABLE_LABEL,
    figure_label: str = DEFAULT_FIGURE_LABEL,
) -> list[Block]:
    """Tokenize a markdown string into blocks."""
    lines = text.splitlines()
    blocks: list[Block] = []
    breakers = _Breakers(table_label=table_label, figure_label=figure_label)

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "<!-- toc -->":
            blocks.append(("toc_marker", None))
            i += 1
            continue
        if stripped == "<!-- references -->":
            blocks.append(("references_marker", None))
            i += 1
            continue

        if (m := _RE_HEADING4.match(line)) is not None:
            blocks.append(("heading4", m.group(1).strip()))
            i += 1
            continue

        if (m := _RE_HEADING3.match(line)) is not None:
            blocks.append(("heading3", m.group(1).strip()))
            i += 1
            continue

        if (m := _RE_HEADING2.match(line)) is not None:
            blocks.append(("heading2", m.group(1).strip()))
            i += 1
            continue

        if _looks_like_table_header(lines, i):
            tlines, i = _consume_table(lines, i)
            blocks.append(("table", tlines))
            continue

        if stripped.startswith(table_label):
            blocks.append(("table_caption", stripped))
            i += 1
            continue

        if _RE_CONTINUATION.match(stripped):
            normalized = re.sub(r"^продолжение", "Продолжение", stripped, flags=re.IGNORECASE)
            blocks.append(("continuation_caption", normalized))
            i += 1
            continue

        if stripped.startswith(figure_label):
            blocks.append(("figure_caption", stripped))
            i += 1
            continue

        if (m := _RE_IMAGE.match(stripped)) is not None:
            blocks.append(("image", (m.group(2), m.group(1))))
            i += 1
            continue

        if (m := _RE_LIST_ITEM.match(stripped)) is not None:
            blocks.append(("list_item", f"{m.group(1)}. {m.group(2)}"))
            i += 1
            continue

        if (m := _RE_BULLET.match(line)) is not None:
            level = _indent_level(m.group(1))
            blocks.append(("bullet", (level, m.group(2))))
            i += 1
            continue

        # Multi-line paragraph: gather contiguous non-block lines.
        plines = [stripped]
        i += 1
        while i < len(lines):
            nxt_line = lines[i]
            nxt = nxt_line.strip()
            if (
                not nxt
                or breakers.matches(nxt)
                or _RE_BULLET.match(nxt_line) is not None
                or _looks_like_table_header(lines, i)
            ):
                break
            plines.append(nxt)
            i += 1
        blocks.append(("paragraph", " ".join(plines)))

    return blocks


def _indent_level(prefix: str) -> int:
    """Translate leading whitespace into a 0-based nesting level."""
    width = 0
    for ch in prefix:
        width += INDENT_SPACES_PER_LEVEL if ch == "\t" else 1
    return width // INDENT_SPACES_PER_LEVEL


def _is_table_separator(line: str) -> bool:
    """Return True if ``line`` is a markdown table-separator row.

    Accepts both bordered (``|---|---|``) and bare (``--- | ---``) styles,
    plus alignment colons (``:---``, ``---:``, ``:---:``).
    """
    s = line.strip()
    if not s:
        return False
    s = s.strip("|").strip()
    if not s:
        return False
    return all(_RE_TABLE_SEP_CELL.match(p.strip()) for p in s.split("|"))


def _looks_like_table_header(lines: list[str], i: int) -> bool:
    """Treat line ``i`` as a table header when the next line is a separator."""
    if i + 1 >= len(lines):
        return False
    if "|" not in lines[i]:
        return False
    return _is_table_separator(lines[i + 1])


def _consume_table(lines: list[str], i: int) -> tuple[list[str], int]:
    """Collect header + separator + body rows starting at ``i``."""
    out: list[str] = []
    # header
    out.append(lines[i].strip())
    i += 1
    # separator
    out.append(lines[i].strip())
    i += 1
    # body rows: any non-blank line that still contains '|'
    while i < len(lines):
        s = lines[i].strip()
        if not s or "|" not in s:
            break
        out.append(s)
        i += 1
    return out, i


class _Breakers:
    """Predicate that decides whether a line ends the current paragraph."""

    def __init__(self, *, table_label: str, figure_label: str) -> None:
        self.table_label = table_label
        self.figure_label = figure_label

    def matches(self, text: str) -> bool:
        return (
            text.startswith("#")
            or text.startswith("|")
            or text.startswith(self.table_label)
            or text.startswith(self.figure_label)
            or _RE_CONTINUATION.match(text) is not None
            or _RE_LIST_ITEM_PARAGRAPH_BREAKER.match(text) is not None
            or text in ("<!-- toc -->", "<!-- references -->")
        )
