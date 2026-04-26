from autodocx.ns import w_tag
from autodocx.tables import _split_cells, build_table


def test_split_cells_strips_outer_pipes():
    assert _split_cells("| a | b | c |") == ["a", "b", "c"]


def test_split_cells_handles_bare_pipes():
    assert _split_cells("a | b | c") == ["a", "b", "c"]


def test_split_cells_collapses_internal_whitespace():
    assert _split_cells("|  a   |   b  |") == ["a", "b"]


def test_build_table_returns_none_for_too_few_lines():
    assert build_table(["| h |", "|---|"]) is None


def test_build_table_emits_header_with_repeat_marker():
    tbl = build_table(["| h1 | h2 |", "|---|---|", "| a | b |"])
    assert tbl is not None
    rows = tbl.findall(w_tag("tr"))
    assert len(rows) == 2  # header + 1 body row
    header_props = rows[0].find(w_tag("trPr"))
    assert header_props is not None
    assert header_props.find(w_tag("tblHeader")) is not None
    assert header_props.find(w_tag("cantSplit")) is not None


def test_build_table_grid_columns_match_header_cells():
    tbl = build_table(["a | b | c", "-- | -- | --", "1 | 2 | 3"])
    assert tbl is not None
    grid_cols = tbl.findall(f"{w_tag('tblGrid')}/{w_tag('gridCol')}")
    assert len(grid_cols) == 3
