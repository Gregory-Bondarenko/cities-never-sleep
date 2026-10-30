from citiesneversleep.sources.wikidata_pop import CITIES_QUERY, POPULATION_QUERY


def test_both_queries_share_city_filter():
    for q in (CITIES_QUERY, POPULATION_QUERY):
        assert "UNION" in q
        assert "wdt:P764 ?oktmo" in q
        assert "FILTER NOT EXISTS { ?city wdt:P17 wd:Q159 . }" in q
    assert "?coverage" in CITIES_QUERY.split("WHERE")[0]
