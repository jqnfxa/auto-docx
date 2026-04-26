# AutoDocx

Render Markdown into a styled `.docx` using a Word template.

AutoDocx walks one or more `.md` files, resolves citations, converts
LaTeX math through `pandoc`, embeds images and tables, then splices the
result into the body of a `.docx` template — preserving styles, headers,
fonts and section properties from the template.

## Features

- Markdown headings → `Heading2`/`Heading3` with configurable centered
  / "title page" overrides.
- Pipe-tables with auto-repeating headers across page breaks.
- Inline images via `![caption](path)` with auto-numbered figure captions.
- BibTeX-flavored citations: `[@key]` → `[N]`, `[@key, p. 84]` → `[N, с. 84]`.
- LaTeX math `$x$` / `$$x$$` rendered through `pandoc` into native OOXML.
- Auto-updating `СОДЕРЖАНИЕ` / TOC field via `<!-- toc -->`.
- Optional `header.docx` prepended for title pages, task pages, etc.
- Stats template variables: `{{n_pages}}`, `{{n_figures}}`, `{{n_tables}}`,
  `{{n_sources}}`.

## Requirements

- Python ≥ 3.11
- [`pandoc`](https://pandoc.org/) on `PATH` (only required if your markdown
  uses LaTeX math)
- [`uv`](https://docs.astral.sh/uv/) — recommended package manager

## Installation

```fish
uv venv
uv pip install git+https://github.com/jqnfxa/AutoDocx
```

Activate the venv (`source .venv/bin/activate.fish`) and run `autodocx --help`.

For local development:

```fish
uv venv
uv pip install -e ".[dev]"
```

## Project layout

AutoDocx expects (but does not enforce) the following folders in the
working directory you run it from:

```
.
├── markdown/         # input *.md and reference.bib
├── pictures/         # images referenced via ![](path)
├── docx/             # template.docx, optional header.docx
└── autodocx.toml     # optional build config
```

## Usage

### One-shot CLI

```fish
autodocx \
    --template docx/template.docx \
    --output output.docx \
    --bib markdown/reference.bib \
    --pictures pictures \
    markdown/intro.md markdown/chapter1.md markdown/chapter2.md
```

### Config-driven

Drop a TOML file describing the build:

```toml
# autodocx.toml
[project]
template = "docx/template.docx"
header = "docx/header.docx"
output = "output.docx"
pictures = "pictures"

[input]
files = [
    "markdown/intro.md",
    "markdown/1.md",
    "markdown/2.md",
    "markdown/3.md",
    "markdown/4.md",
    "markdown/5.md",
    "markdown/6.md",
    "markdown/conclusion.md",
]
bibliography = "markdown/reference.bib"

[render]
# Headings rendered as bold-centered BodyText (skipping Heading2 numbering)
title_pages = ["РЕФЕРАТ", "ABSTRACT", "СОДЕРЖАНИЕ"]
# Headings rendered as Heading2 + centered, no numbering
centered_headings = [
    "ВВЕДЕНИЕ",
    "ЗАКЛЮЧЕНИЕ",
    "ОПРЕДЕЛЕНИЯ, ОБОЗНАЧЕНИЯ И СОКРАЩЕНИЯ",
    "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ",
]
references_heading = "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ"
toc_heading = "СОДЕРЖАНИЕ"
figure_label = "Рисунок"
table_label = "Таблица"

[stats]
manual_pages = 50
```

Then:

```fish
autodocx --config autodocx.toml
```

CLI flags (`--template`, `--output`, `--bib`, …) override values loaded
from the TOML file.

## Markdown conventions

| Markdown                            | Output                                             |
| ----------------------------------- | -------------------------------------------------- |
| `# Title`                           | `Heading2` paragraph                               |
| `## Section`                        | `Heading3` paragraph                               |
| `**bold**`                          | bold run                                           |
| `- item`                            | bullet                                             |
| `1. item`                           | numbered list item (manual prefix)                 |
| `\| h1 \| h2 \|` + sep + rows       | borders, repeating header `w:tbl`                  |
| `![caption](path)`                  | inline image + auto-numbered figure caption        |
| `Таблица 3 — caption`               | left-aligned table caption (`Style14`)             |
| `Рисунок 5 — caption`               | centered figure caption (`Style15`)                |
| `[@bibkey]` / `[@key, p. 84]`       | citation resolved against `--bib`                  |
| `$x$`, `$$x$$`                      | OMML formula (requires `pandoc`)                   |
| `<!-- toc -->`                      | auto-updating TOC field                            |
| `<!-- references -->`               | (reserved; references are appended automatically)  |
| `{{n_pages}}` / `{{n_figures}}` …   | substituted with computed counts before parsing    |

## Reproducing the legacy VKR pipeline

The original `build_docx.py` produced a Russian-language thesis with a
fixed file list and hardcoded section names. To reproduce that output:

1. Place `intro.md` / `1.md` … `6.md` / `conclusion.md` in `markdown/`.
2. Place images in `pictures/`.
3. Place `template.docx` (and optional `header.docx`) in `docx/`.
4. Use the `autodocx.toml` shown above.
5. In `intro.md`, replace the hand-typed stats line with the templated
   form:

   ```
   Пояснительная записка {{n_pages}} стр., {{n_figures}} рис., {{n_tables}} табл., {{n_sources}} ист.
   ```

6. Run `autodocx --config autodocx.toml`.

The output should match the legacy build (open in Word/LibreOffice and
press `Ctrl+A` then `F9` to refresh the TOC and page numbers).

## License

MIT — see [LICENSE](LICENSE).
