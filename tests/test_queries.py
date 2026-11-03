from citiesneversleep.sources.wikidata_pop import CITIES_QUERY, POPULATION_QUERY


def test_both_queries_share_city_filter():
    for q in (CITIES_QUERY, POPULATION_QUERY):
        assert "UNION" in q
        assert "wdt:P764 ?oktmo" in q
        assert "hint:optimizer" in q  # порядок троек задан вручную
        assert "FILTER NOT EXISTS { ?city wdt:P17 wd:Q159 . }" in q
    assert "?coverage" in CITIES_QUERY.split("WHERE")[0]


def test_city_class_uses_all_ranks():
    """Класс берётся из всех утверждений P31, а не только из лучшего ранга (#48)."""
    from citiesneversleep.sources.wikidata_pop import CITY_CLASSES, CITY_FILTER

    assert "wdt:P31 wd:Q7930989" not in CITY_FILTER
    assert "?city p:P31 ?st" in CITY_FILTER and "DeprecatedRank" in CITY_FILTER
    for q in ("Q7930989", "Q515", "Q106389302", "Q1549591"):
        assert q in CITY_CLASSES and f"wd:{q}" in CITY_FILTER
    for query in (CITIES_QUERY, POPULATION_QUERY):
        assert "SELECT DISTINCT" in query


def test_missing_control_cities():
    from citiesneversleep.sources.wikidata_pop import CONTROL_CITIES, missing_control_cities

    assert missing_control_cities(CONTROL_CITIES) == {}
    assert missing_control_cities(["Q649"])["Q887"] == "Екатеринбург"


def test_rural_filters():
    from citiesneversleep.sources.wikidata_pop import CITY_FILTER, is_rural_oktmo

    assert "pq:P582" in CITY_FILTER and "wd:Q532" in CITY_FILTER
    assert is_rural_oktmo("96634420101")  # сельское поселение в районе
    assert not is_rural_oktmo("22605101001")  # городское поселение
    assert not is_rural_oktmo("03701000001")  # городской округ
    assert not is_rural_oktmo(None) and not is_rural_oktmo("4570")
