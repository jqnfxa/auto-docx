# AutoDocx

Render Markdown into a styled `.docx` using a Word template.

AutoDocx walks one or more `.md` files, resolves citations, converts
LaTeX math through `pandoc`, embeds images and tables, then splices the
result into the body of a `.docx` template — preserving styles, headers,
fonts and section properties from the template.

## Features

- Markdown headings (`#`/`##`/`###`) → `Heading2` / `Heading3` / `Heading4`
  with configurable centered / "title page" overrides.
- Pipe-tables in both bordered (`| h | h |`) and bare (`h | h`) styles, with
  auto-repeating header rows across page breaks.
- Inline images via `![caption](path)` with auto-numbered figure captions.
- Nested bullets (`-` / `*`) — three levels of markers (`•`, `○`, `▪`) at
  1.25 cm-per-level indents.
- BibTeX-flavored citations: `[@key]` → `[N]`, `[@key, p. 84]` → `[N, с. 84]`.
- LaTeX math `$x$` / `$$x$$` rendered through `pandoc` into native OOXML.
- Auto-updating TOC field via the `<!-- toc -->` marker.
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

Activate the venv and run `autodocx --help`.

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

Drop a TOML file describing the build. The example shipped at the repo
root (`autodocx.toml`) renders the sample document under `markdown/` +
`pictures/` + `docx/` against the supplied template:

```toml
# autodocx.toml
[project]
template = "docx/template.docx"
# Optional: a separate .docx whose body is prepended to the output —
# typically a title page, signed task, or calendar plan. Its styles,
# fonts, footers, footnotes, and embedded media are forwarded so the
# prepended content keeps its original formatting.
header = "docx/header.docx"
output = "output.docx"
pictures = "pictures"

[input]
files = [
    "markdown/abstract.md",
    "markdown/table_of_contents.md",
    "markdown/definitions.md",
    "markdown/intro.md",
    "markdown/1.md",
    "markdown/conclusion.md",
]

[render]
# Headings rendered as bold-centered BodyText (skipping Heading2 numbering)
title_pages = ["РЕФЕРАТ", "ABSTRACT", "СОДЕРЖАНИЕ"]
# Headings rendered as Heading2 + centered, no numbering
centered_headings = [
    "ОПРЕДЕЛЕНИЯ, ОБОЗНАЧЕНИЯ И СОКРАЩЕНИЯ (заголовок второго уровня)",
    "ВВЕДЕНИЕ (заголовок второго уровня)",
    "ЗАКЛЮЧЕНИЕ (заголовок второго уровня)",
    "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ",
]
references_heading = "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ"

[stats]
manual_pages = 10
```

Drop `header = …` (or comment it out) if you don't want a prepended
document. The CLI equivalent is `--header docx/header.docx`, which
overrides the TOML value.

Other optional fields not shown:

- `[input] bibliography = "markdown/reference.bib"` — BibTeX file used to
  resolve `[@key]` citations.
- `[render] figure_label`, `table_label` — caption prefixes (default
  `Рисунок` / `Таблица`).

Build it:

```fish
autodocx --config autodocx.toml
```

CLI flags (`--template`, `--output`, `--bib`, …) override values loaded
from the TOML file.

After building, open `output.docx` in Word or LibreOffice and press
`Ctrl+A` then `F9` to refresh the TOC and page numbers.

## Markdown conventions

| Markdown                            | Output                                             |
| ----------------------------------- | -------------------------------------------------- |
| `# Title`                           | `Heading2` paragraph                               |
| `## Section`                        | `Heading3` paragraph                               |
| `### Subsection`                    | `Heading4` paragraph                               |
| `**bold**`                          | bold run                                           |
| `- item` / `  - nested`             | bulleted paragraph; 2-space indent steps the level |
| `1. item`                           | numbered list item (manual prefix)                 |
| `\| h \| h \|` or `h \| h` + sep    | borders, repeating header `w:tbl`                  |
| `![caption](path)`                  | inline image + auto-numbered figure caption        |
| `Таблица 3 — caption`               | left-aligned table caption (`Style14`)             |
| `Рисунок 5 — caption`               | centered figure caption (`Style15`)                |
| `[@bibkey]` / `[@key, p. 84]`       | citation resolved against `--bib`                  |
| `$x$`, `$$x$$`                      | OMML formula (requires `pandoc`)                   |
| `<!-- toc -->`                      | auto-updating TOC field                            |
| `<!-- references -->`               | (reserved; references are appended automatically)  |
| `{{n_pages}}` / `{{n_figures}}` …   | substituted with computed counts before parsing    |

## License

MIT — see [LICENSE](LICENSE).
