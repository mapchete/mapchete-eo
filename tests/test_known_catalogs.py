import pytest

from mapchete_eo.known_catalogs import (
    AWSSearchCatalogS2L2A,
    CDSESearch,
    EarthSearchV1S2L2A,
    PlanetaryComputerSearch,
)
from mapchete_eo.types import TimeRange


@pytest.mark.remote
def test_e84_cog_catalog_search_items(e84_cog_catalog):
    assert (
        len(
            list(
                e84_cog_catalog.search(
                    time=TimeRange(
                        start="2022-06-01",
                        end="2022-06-06",
                    ),
                    bounds=[16, 46, 17, 47],
                )
            )
        )
        > 0
    )


@pytest.mark.remote
def test_e84_cog_catalog_eo_bands(e84_cog_catalog):
    assert len(e84_cog_catalog.eo_bands) > 0


@pytest.mark.skip(reason="This test is flaky.")
@pytest.mark.remote
def test_utm_search_catalog_search_items(utm_search_catalog):
    assert (
        len(
            list(
                utm_search_catalog.search(
                    time=TimeRange(
                        start="2022-06-05",
                        end="2022-06-05",
                    ),
                    bounds=[-180, 65, -179, 65.3],
                )
            )
        )
        > 0
    )


@pytest.mark.remote
@pytest.mark.parametrize(
    "catalog_cls,collection_name",
    [
        (EarthSearchV1S2L2A, "sentinel-2-l2a"),
        (CDSESearch, "sentinel-2-l2a"),
        (AWSSearchCatalogS2L2A, "sentinel-s2-l2a"),
        (PlanetaryComputerSearch, "sentinel-2-l2a"),
    ],
)
def test_known_catalogs(catalog_cls, collection_name):
    catalog = catalog_cls(
        collections=[collection_name],
    )
    items = catalog.search(
        time=TimeRange(
            start="2022-06-05",
            end="2022-06-05",
        ),
        bounds=[-180, 65, -179, 65.3],
    )
    assert items
