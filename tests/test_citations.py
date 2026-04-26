from autodocx.citations import (
    CitationResolver,
    _format_entry,
    _format_urldate,
    _initials_first_list,
    _surname_first_list,
)


def test_split_authors_into_surname_first_list():
    result = _surname_first_list("Бобкова, О.В. and Давыдов, С.А.")
    assert result == "Бобкова, О.В., Давыдов, С.А."


def test_split_authors_into_initials_first_list():
    result = _initials_first_list("Бобкова, О.В. and Давыдов, С.А.")
    assert result == "О.В. Бобкова, С.А. Давыдов"


def test_format_urldate_iso_to_dotted():
    assert _format_urldate("2021-04-28") == "28.04.2021"
    assert _format_urldate("2021/04/28") == "28.04.2021"
    assert _format_urldate("2021-4-8") == "08.04.2021"


def test_format_urldate_passes_through_unparseable():
    assert _format_urldate("28.04.2021") == "28.04.2021"


def test_format_article_emits_full_gost_shape():
    result = _format_entry(
        "article",
        {
            "author": "Бобкова, О.В. and Давыдов, С.А. and Ковалева, И.А.",
            "title": "Плагиат как гражданское правонарушение",
            "journal": "Патенты и лицензии",
            "year": "2016",
            "number": "7",
            "pages": "31-37",
        },
    )
    assert result == (
        "Бобкова, О.В., Давыдов, С.А., Ковалева, И.А., "
        "Плагиат как гражданское правонарушение / "
        "О.В. Бобкова, С.А. Давыдов, И.А. Ковалева"
        " // Патенты и лицензии. – 2016. – № 7. – С. 31-37."
    )


def test_format_online_with_urldate():
    result = _format_entry(
        "online",
        {
            "title": "The State of the Octoverse",
            "url": "https://octoverse.github.com",
            "urldate": "2021-04-28",
        },
    )
    assert result == (
        "The State of the Octoverse [Электронный ресурс]. "
        "URL: https://octoverse.github.com (дата обращения: 28.04.2021)."
    )


def test_collect_citations_assigns_numbers_in_order(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@online{octo, title = {O}, url = {u}}\n"
        "@article{bob, author = {A}, title = {T}, journal = {J}, year = {2020}}\n",
        encoding="utf-8",
    )
    citer = CitationResolver(bib)
    citer.collect_citations("see [@octo] and later [@bob], also [@octo] again")
    assert citer.cited_keys == {"octo": 1, "bob": 2}


def test_resolve_citations_inline_and_grouped(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@online{a, title = {A}}\n@online{b, title = {B}}\n",
        encoding="utf-8",
    )
    citer = CitationResolver(bib)
    citer.collect_citations("[@a] and [@b]")
    assert citer.resolve_citations("see [@a] and [@b]") == "see [1] and [2]"
    assert citer.resolve_citations("[@a; @b]") == "[1, 2]"
    assert citer.resolve_citations("[@a, p. 84]") == "[1, с. 84]"


def test_resolve_unknown_key_marks_with_question_mark(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text("@online{known, title = {K}}\n", encoding="utf-8")
    citer = CitationResolver(bib)
    # Don't collect; resolve still returns ? for unknown keys.
    assert citer.resolve_citations("[@unknown]") == "[?]"


def test_get_reference_list_orders_by_first_citation(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@online{a, title = {Alpha}}\n@online{b, title = {Beta}}\n",
        encoding="utf-8",
    )
    citer = CitationResolver(bib)
    citer.collect_citations("[@b]")
    citer.collect_citations("[@a]")
    refs = citer.get_reference_list()
    assert [n for n, _ in refs] == [1, 2]
    assert "Beta" in refs[0][1]
    assert "Alpha" in refs[1][1]
