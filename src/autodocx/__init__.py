"""Render Markdown into a styled .docx using a Word template."""

__version__ = "0.1.0"

from autodocx.config import BuildConfig
from autodocx.pipeline import build_document

__all__ = ["BuildConfig", "__version__", "build_document"]
