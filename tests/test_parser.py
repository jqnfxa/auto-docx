from autodocx.parser import _indent_level, _is_table_separator, parse_md_text


def test_headings_distinguished_by_level():
    blocks = parse_md_text("# H2\n## H3\n### H4\n")
    assert blocks == [("heading2", "H2"), ("heading3", "H3"), ("heading4", "H4")]


def test_paragraph_collects_continuation_lines():
    blocks = parse_md_text("First line\nsecond line\nthird line\n")
    assert blocks == [("paragraph", "First line second line third line")]


def test_blank_line_breaks_paragraph():
    blocks = parse_md_text("first\n\nsecond\n")
    assert blocks == [("paragraph", "first"), ("paragraph", "second")]


def test_bullet_indent_maps_to_level():
    blocks = parse_md_text("- top\n  - sub\n    - subsub\n- back\n")
    assert blocks == [
        ("bullet", (0, "top")),
        ("bullet", (1, "sub")),
        ("bullet", (2, "subsub")),
        ("bullet", (0, "back")),
    ]


def test_bullet_accepts_asterisk_and_dash():
    blocks = parse_md_text("- a\n* b\n")
    assert blocks == [("bullet", (0, "a")), ("bullet", (0, "b"))]


def test_bordered_table_parses_with_separator():
    md = "| h1 | h2 |\n|---|---|\n| a | b |\n"
    [(kind, lines)] = parse_md_text(md)
    assert kind == "table"
    assert lines == ["| h1 | h2 |", "|---|---|", "| a | b |"]


def test_bare_pipe_table_parses_too():
    md = "h1 | h2 | h3\n-- | -- | --\nx | y | z\n"
    [(kind, lines)] = parse_md_text(md)
    assert kind == "table"
    assert lines[0] == "h1 | h2 | h3"
    assert lines[-1] == "x | y | z"


def test_table_caption_and_continuation():
    md = "Таблица 1 — caption\nПродолжение таблицы 1\n"
    blocks = parse_md_text(md)
    assert blocks == [
        ("table_caption", "Таблица 1 — caption"),
        ("continuation_caption", "Продолжение таблицы 1"),
    ]


def test_continuation_caption_normalized_to_capital():
    blocks = parse_md_text("продолжение таблицы 1\n")
    assert blocks == [("continuation_caption", "Продолжение таблицы 1")]


def test_image_block_unpacks_path_and_caption():
    blocks = parse_md_text("![alt text](pictures/logo.png)\n")
    assert blocks == [("image", ("pictures/logo.png", "alt text"))]


def test_html_comment_markers_emit_typed_blocks():
    blocks = parse_md_text("<!-- toc -->\n<!-- references -->\n")
    assert blocks == [("toc_marker", None), ("references_marker", None)]


def test_numbered_text_mid_paragraph_does_not_start_a_list():
    # CommonMark: only "1." can interrupt a paragraph; "12." mustn't.
    md = "Some sentence ending with size\n12. Other sentence continues here.\n"
    [(kind, text)] = parse_md_text(md)
    assert kind == "paragraph"
    assert "12. Other sentence" in text


def test_one_dot_prefix_does_break_paragraph():
    md = "First sentence\n1. List item starting at one\n"
    blocks = parse_md_text(md)
    assert blocks[0][0] == "paragraph"
    assert blocks[1] == ("list_item", "1. List item starting at one")


def test_indent_level_counts_tabs_as_two_spaces():
    assert _indent_level("") == 0
    assert _indent_level("  ") == 1
    assert _indent_level("    ") == 2
    assert _indent_level("\t") == 1
    assert _indent_level("\t\t") == 2


def test_table_separator_detector_accepts_alignment_colons():
    assert _is_table_separator("|---|---|")
    assert _is_table_separator("--- | ---")
    assert _is_table_separator(":---: | ---:")
    assert not _is_table_separator("not a separator")
    assert not _is_table_separator("")
