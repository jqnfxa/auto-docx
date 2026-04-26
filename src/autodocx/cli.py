"""Command-line entry point for the ``autodocx`` console script."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from autodocx import __version__
from autodocx.config import BuildConfig
from autodocx.pipeline import build_document


def main(argv: list[str] | None = None) -> int:
    parser = _make_parser()
    args = parser.parse_args(argv)

    try:
        config = _config_from_args(args)
        build_document(config)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="autodocx",
        description="Render markdown into a styled .docx using a Word template.",
    )
    p.add_argument("--version", action="version", version=f"autodocx {__version__}")

    p.add_argument(
        "-c", "--config",
        type=Path,
        help="Path to a TOML config file. CLI flags override values loaded from it.",
    )
    p.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="Markdown files to render, in order.",
    )
    p.add_argument(
        "-t", "--template",
        type=Path,
        help="Path to the Word template (default: docx/template.docx).",
    )
    p.add_argument(
        "-H", "--header",
        type=Path,
        help="Optional header .docx (e.g. title page) prepended to the output.",
    )
    p.add_argument(
        "-o", "--output",
        type=Path,
        help="Output .docx path (default: output.docx).",
    )
    p.add_argument(
        "--bib",
        type=Path,
        help="BibTeX file used to resolve [@key] citations.",
    )
    p.add_argument(
        "--pictures",
        type=Path,
        help="Directory holding images referenced by markdown (default: pictures/).",
    )
    p.add_argument(
        "--manual-pages",
        type=int,
        help="Manual page-count value substituted for {{n_pages}} in markdown.",
    )
    return p


def _config_from_args(args: argparse.Namespace) -> BuildConfig:
    if args.config:
        config = BuildConfig.from_toml(args.config)
    else:
        if not args.inputs:
            raise FileNotFoundError(
                "no input files given; pass markdown files positionally or use --config"
            )
        config = BuildConfig(
            inputs=[_resolve(p) for p in args.inputs],
            template=_resolve(args.template or Path("docx/template.docx")),
        )

    # CLI overrides
    if args.inputs:
        config.inputs = [_resolve(p) for p in args.inputs]
    if args.template is not None:
        config.template = _resolve(args.template)
    if args.header is not None:
        config.header = _resolve(args.header)
    if args.output is not None:
        config.output = _resolve(args.output)
    if args.bib is not None:
        config.bibliography = _resolve(args.bib)
    if args.pictures is not None:
        config.pictures_dir = _resolve(args.pictures)
    if args.manual_pages is not None:
        config.manual_pages = args.manual_pages

    return config


def _resolve(p: Path) -> Path:
    return p if p.is_absolute() else (Path.cwd() / p)


if __name__ == "__main__":
    raise SystemExit(main())
