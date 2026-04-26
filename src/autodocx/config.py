"""Build-time configuration loaded from CLI args and/or a TOML file.

Layout convention used throughout the docs:

- ``markdown/`` — input ``.md`` and ``.bib`` files
- ``pictures/`` — images referenced by ``![]()`` markdown
- ``docx/`` — the Word template plus optional header documents
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BuildConfig:
    """All inputs needed to render a document.

    Paths are resolved against ``base_dir`` (the directory the config was
    loaded from, or the current working directory when constructed manually).
    """

    inputs: list[Path]
    template: Path
    output: Path = Path("output.docx")
    header: Path | None = None
    bibliography: Path | None = None
    pictures_dir: Path = Path("pictures")
    base_dir: Path = field(default_factory=Path.cwd)

    # Heading rendering rules.
    title_pages: list[str] = field(default_factory=list)
    centered_headings: list[str] = field(default_factory=list)

    # Caption labels (used during parsing and figure auto-numbering).
    figure_label: str = "Рисунок"
    table_label: str = "Таблица"

    # Stats template substitution: occurrences of ``{{n_pages}}``,
    # ``{{n_figures}}``, ``{{n_tables}}``, ``{{n_sources}}`` in markdown
    # bodies are replaced before parsing.
    manual_pages: int | None = None

    @classmethod
    def from_toml(cls, path: str | Path) -> BuildConfig:
        path = Path(path).resolve()
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        base = path.parent
        return cls._from_dict(data, base)

    @classmethod
    def _from_dict(cls, data: dict, base: Path) -> BuildConfig:
        project = data.get("project", {})
        inputs = data.get("input", {})
        render = data.get("render", {})
        stats = data.get("stats", {})

        def resolve(p: str | None) -> Path | None:
            if p is None:
                return None
            pp = Path(p)
            return pp if pp.is_absolute() else (base / pp)

        files = inputs.get("files", [])
        return cls(
            inputs=[resolve(p) for p in files if p],  # type: ignore[misc]
            template=resolve(project.get("template", "docx/template.docx")),  # type: ignore[arg-type]
            output=resolve(project.get("output", "output.docx")),  # type: ignore[arg-type]
            header=resolve(project.get("header")),
            bibliography=resolve(inputs.get("bibliography")),
            pictures_dir=resolve(project.get("pictures", "pictures")),  # type: ignore[arg-type]
            base_dir=base,
            title_pages=list(render.get("title_pages", [])),
            centered_headings=list(render.get("centered_headings", [])),
            figure_label=render.get("figure_label", "Рисунок"),
            table_label=render.get("table_label", "Таблица"),
            manual_pages=stats.get("manual_pages"),
        )

    @property
    def title_page_set(self) -> frozenset[str]:
        return frozenset(self.title_pages)

    @property
    def centered_heading_set(self) -> frozenset[str]:
        return frozenset(self.centered_headings)
