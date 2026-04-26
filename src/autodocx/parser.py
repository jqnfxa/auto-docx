"""Parse a Markdown source file into a flat list of typed blocks.

Each block is a tuple ``(kind, data)`` consumed by :mod:`autodocx.renderer`:

- ``("heading2", text)`` / ``("heading3", text)``
- ``("paragraph", text)`` / ``("bullet", text)`` / ``("list_item", text)``
- ``("table", lines)`` — raw markdown table lines
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
_RE_HEADING3 = re.compile(r"^## (.*)$")
_RE_LIST_ITEM = re.compile(r"^(\d+)\.\s+(.*)$")
_RE_IMAGE = re.compile(r"^!\[(.*?)\]\(([^)]+)\)(?:\{[^}]*\})?\s*$")
_RE_CONTINUATION = re.compile(r"^продолжение таблицы\s", re.IGNORECASE)
_RE_TABLE_LINE = re.compile(r"^\|")
_RE_BULLET = re.compile(r"^- (.*)$")

# Configurable label prefixes for figure/table captions. Russian defaults
# match the original VKR pipeline; pass overrides via parse_md if needed.
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

        if (m := _RE_HEADING3.match(line)) is not None:
            blocks.append(("heading3", m.group(1).strip()))
            i += 1
            continue

        if (m := _RE_HEADING2.match(line)) is not None:
            blocks.append(("heading2", m.group(1).strip()))
            i += 1
            continue

        if _RE_TABLE_LINE.match(line):
            tlines: list[str] = []
            while i < len(lines) and _RE_TABLE_LINE.match(lines[i].strip()):
                tlines.append(lines[i].strip())
                i += 1
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

        if (m := _RE_BULLET.match(stripped)) is not None:
            blocks.append(("bullet", m.group(1)))
            i += 1
            continue

        # Multi-line paragraph: gather contiguous non-block lines.
        plines = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if not nxt or breakers.matches(nxt):
                break
            plines.append(nxt)
            i += 1
        blocks.append(("paragraph", " ".join(plines)))

    return blocks


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
            or _RE_LIST_ITEM.match(text) is not None
            or text.startswith("- ")
            or text in ("<!-- toc -->", "<!-- references -->")
        )
