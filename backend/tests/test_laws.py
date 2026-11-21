from app.services.laws import LawChunk, LocalLawIndex, load_default_index, tokenize

LISTED_ACTS = {
    "Kodeks pracy",
    "ustawa zasiłkowa",
    "ustawa o świadczeniach rodzinnych",
    "ustawa o pomocy państwa w wychowywaniu dzieci (800+)",
    "Prawo oświatowe (rekrutacja)",
    "ustawa o opiece nad dziećmi w wieku do lat 3",
    "ustawa „Za życiem”",
    "ustawa o Karcie Dużej Rodziny",
}


def _chunk(i: str, article: str, text: str, act: str = "Akt testowy") -> LawChunk:
    return LawChunk(id=i, act=act, act_short=act, article=article, text=text, url="https://isap.sejm.gov.pl/x")


def test_search_finds_macierzynski_article():
    results = load_default_index().search("urlop macierzyński", k=5)
    assert results
    assert any(c.act_short == "Kodeks pracy" and c.article == "Art. 180" for c in load_default_index().search("urlop macierzyński wymiar tygodni", k=5))
    assert any("macierzy" in c.text.lower() for c in results)


def test_search_polish_diacritics_insensitive():
    index = load_default_index()
    with_diacritics = [c.id for c in index.search("zasiłek macierzyński", k=5)]
    without = [c.id for c in index.search("zasilek macierzynski", k=5)]
    assert with_diacritics == without and with_diacritics


def test_search_matches_inflected_forms():
    index = LocalLawIndex([_chunk("a", "Art. 1", "Pracownicy przysługuje urlop macierzyński."), _chunk("b", "Art. 2", "Zupełnie inny temat.")])
    assert [c.id for c in index.search("macierzyńskiego", k=3)] == ["a"]


def test_results_have_url_and_article():
    for c in load_default_index().search("świadczenie wychowawcze 800+", k=5):
        assert c.url.startswith("https://")
        assert c.article.startswith("Art. ")
        assert c.text.startswith(c.article)


def test_empty_query_returns_empty():
    index = load_default_index()
    assert index.search("") == []
    assert index.search("   ") == []
    assert index.search("i w z") == []  # same słowa funkcyjne
    assert index.search("urlop", k=0) == []


def test_no_match_returns_empty():
    assert load_default_index().search("zzzzqqqq xylofon") == []


def test_default_index_covers_all_listed_acts():
    assert load_default_index().acts == LISTED_ACTS


def test_default_index_has_no_broken_text():
    chunks = load_default_index().chunks
    assert len(chunks) > 250
    assert len({c.id for c in chunks}) == len(chunks)
    # artefakty ekstrakcji PDF („macierzy ńskiego”) nie mogą zostać
    assert not any("macierzy ńskiego" in c.text or "zako ńczenia" in c.text for c in chunks)


def test_ranking_is_stable_and_respects_k():
    index = load_default_index()
    assert [c.id for c in index.search("urlop", k=3)] == [c.id for c in index.search("urlop", k=3)]
    assert len(index.search("urlop", k=2)) == 2


def test_tokenize_normalizes():
    assert tokenize("Łódź, ŻÓŁĆ!") == ["lodz", "zolc"]
    assert tokenize("macierzyńskiego") == tokenize("macierzyństwo") == ["macie"]
