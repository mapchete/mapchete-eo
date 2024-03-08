import pytest
from pytest_lazyfixture import lazy_fixture
from shapely.geometry import shape

from mapchete_eo.search.s2_mgrs import S2Tile, s2_tiles_from_bounds


@pytest.mark.parametrize(
    "item",
    [
        lazy_fixture("stac_item_pb0214"),
        lazy_fixture("stac_item_pb0300"),
        lazy_fixture("stac_item_pb0301"),
        lazy_fixture("stac_item_pb0400"),
        lazy_fixture("stac_item_pb0400_offset"),
        lazy_fixture("stac_item_pb0509"),
    ],
)
def test_s2tile_bounds(item):
    s2tile = S2Tile(
        utm_zone=str(item.properties["mgrs:utm_zone"]),
        latitude_band=item.properties["mgrs:latitude_band"],
        grid_square=item.properties["mgrs:grid_square"],
    )
    from mapchete.io import rasterio_open

    with rasterio_open(item.assets["red"].href) as src:
        print(src.transform)
        print(src.bounds)
        print(src.bounds.left)
        print(src.bounds.bottom - 9_800)
    intersection_area = shape(item.geometry).intersection(shape(s2tile.latlon_geom()))
    assert intersection_area < 0.001


def test_s2_tiles_from_bounds():
    tiles = s2_tiles_from_bounds(0.72796, 47.36041, 3.68207, 50.24650, crs="EPSG:4326")
    for tile in tiles:
        print(tile)
    assert set(tiles) == set(
        [
            S2Tile.from_tile_id("31UCR"),
            S2Tile.from_tile_id("31UDR"),
            S2Tile.from_tile_id("31UER"),
            S2Tile.from_tile_id("31UEQ"),
            S2Tile.from_tile_id("31UEP"),
            S2Tile.from_tile_id("31UDP"),
            S2Tile.from_tile_id("31UDQ"),
            S2Tile.from_tile_id("31UCQ"),
            S2Tile.from_tile_id("31TCN"),
            S2Tile.from_tile_id("31TDN"),
            S2Tile.from_tile_id("31TEN"),
        ]
    )
