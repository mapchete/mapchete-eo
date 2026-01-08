import pytest
from mapchete_eo.source import Source
from mapchete_eo.search import STACStaticCollection, UTMSearchCatalog
from mapchete_eo.search.config import quote_cql_query
from mapchete_eo.types import TimeRange


@pytest.mark.parametrize(
    "query, expected_len",
    [
        ("eo:cloud_cover < 100", 10),
        ("eo:cloud_cover < 10", 6),
        ("eo:cloud_cover < 1", 2),
        ("eo:cloud_cover = 0", 0),
    ],
)
def test_source_search_unquoted_query(s2_stac_collection, query, expected_len):
    source = Source(collection=str(s2_stac_collection), query=query)
    items = list(source.search(time=TimeRange(start="2023-08-01", end="2023-08-31")))
    assert len(items) == expected_len


@pytest.mark.parametrize(
    "query, expected_len",
    [
        ("eo:cloud_cover < 100", 10),
        ("eo:cloud_cover < 10", 6),
        ("eo:cloud_cover < 1", 2),
        ("eo:cloud_cover = 0", 0),
    ],
)
def test_static_search_unquoted_query(s2_stac_collection, query, expected_len):
    catalog = STACStaticCollection(str(s2_stac_collection))
    items = list(catalog.search(query=query))
    assert len(items) == expected_len


@pytest.mark.parametrize(
    "query, expected_len",
    [
        ("eo:cloud_cover < 100", 6),
        ("eo:cloud_cover < 50", 5),
        ("eo:cloud_cover < 20", 2),
        ("eo:cloud_cover = 0", 0),
    ],
)
def test_utm_search_unquoted_query(query, expected_len):
    catalog = UTMSearchCatalog(
        collection="https://sentinel-s2-l2a-stac.s3.amazonaws.com/sentinel-s2-l2a.json"
    )
    items = list(
        catalog.search(
            time=TimeRange(start="2022-06-06", end="2022-06-06"),
            bounds=[16, 46, 17, 47],
            query=query,
        )
    )
    assert len(items) == expected_len


def test_quote_cql_query_logic():
    assert quote_cql_query("eo:cloud_cover < 10") == '"eo:cloud_cover" < 10'
    assert (
        quote_cql_query("eo:cloud_cover < 10 AND s2:datastrip_id = 'foo'")
        == '"eo:cloud_cover" < 10 AND "s2:datastrip_id" = \'foo\''
    )
    assert quote_cql_query('"eo:cloud_cover" < 10') == '"eo:cloud_cover" < 10'
    assert quote_cql_query("cloud_cover < 10") == "cloud_cover < 10"
