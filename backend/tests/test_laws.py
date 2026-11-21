from app.services.laws import LawChunk, LocalLawIndex, load_default_index


def chunk(id_: str, text: str, article: str = "Art. 1", act: str = "Ustawa testowa") -> LawChunk:
    return LawChunk(id=id_, act=act, act_short="UT", article=article, text=text, url="https://example.gov.pl/akt")


def small_index() -> LocalLawIndex:
    return LocalLawIndex(
        [
            chunk("a", "Pracownicy przysługuje urlop macierzyński w wymiarze 20 tygodni.", "Art. 180"),
            chunk("b", "Zasiłek pogrzebowy przysługuje w kwocie 4000 zł.", "Art. 10"),
            chunk("c", "Dziecko może być przyjęte do przedszkola publicznego w drodze rekrutacji.", "Art. 130"),
        ]
    )


def test_search_finds_macierzynski_article():
    hits = load_default_index().search("urlop macierzyński wymiar tygodni", k=5)
    assert hits, "indeks powinien znaleźć przepisy o urlopie macierzyńskim"
    assert any(h.act_short == "KP" and h.article == "Art. 180" for h in hits[:3])


def test_search_polish_diacritics_insensitive():
    idx = small_index()
    with_ogonki = [h.id for h in idx.search("urlop macierzyński")]
    without = [h.id for h in idx.search("urlop macierzynski")]
    assert with_ogonki == without and with_ogonki[0] == "a"
    assert idx.search("ZASIŁEK pogrzebowy")[0].id == "b"


def test_prefix_stemming_matches_inflected_forms():
    idx = small_index()
    # „przedszkolu” / „przedszkola” / „przedszkole” mają wspólny przedrostek 5 znaków
    assert idx.search("przedszkole rekrutacja")[0].id == "c"
    assert idx.search("rekrutacji do przedszkoli")[0].id == "c"


def test_results_have_url_and_article():
    for h in load_default_index().search("zasiłek macierzyński", k=5):
        assert h.url.startswith("https://")
        assert h.article.startswith("Art. ")
        assert h.act and h.act_short and h.text


def test_empty_query_returns_empty():
    idx = small_index()
    assert idx.search("") == []
    assert idx.search("   ") == []
    assert idx.search("???") == []
    assert idx.search("a w z") == []  # same stop-słowa / zbyt krótkie tokeny


def test_no_match_returns_empty():
    assert small_index().search("kryptowaluty blockchain") == []


def test_k_limits_results():
    assert len(load_default_index().search("dziecko", k=3)) == 3


def test_article_number_in_query_boosts_that_article():
    hits = load_default_index().search("art. 180 kodeks pracy", k=3)
    assert hits[0].article == "Art. 180" and hits[0].act_short == "KP"


def test_default_index_covers_all_listed_acts():
    idx = load_default_index()
    shorts = {c.act_short for c in idx.chunks}
    assert len(shorts) == 8
    joined = " ".join(c.act for c in idx.chunks)
    for needle in (
        "Kodeks pracy",
        "choroby i macierzyństwa",
        "świadczeniach rodzinnych",
        "wychowywaniu dzieci",
        "Prawo oświatowe",
        "do lat 3",
        "Za życiem",
        "Karcie Dużej Rodziny",
    ):
        assert needle in joined, needle


def test_chunk_ids_unique():
    ids = [c.id for c in load_default_index().chunks]
    assert len(ids) == len(set(ids))
