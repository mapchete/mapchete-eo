import pytest
from mapchete.io.vector import reproject_geometry, segmentize_geometry
from pytest_lazyfixture import lazy_fixture
from shapely import equals
from shapely.geometry import box, shape

from mapchete_eo.search.s2_mgrs import S2Tile, s2_tiles_from_bounds


def _reverse_engineer_source(item, s2tile):
    """Find out source coordinates of square grid."""
    from mapchete.io import rasterio_open
    from mapchete.types import Bounds

    TILE_WIDTH_M = 100_000
    TILE_HEIGHT_M = 100_000
    # overlap for bottom and right
    TILE_OVERLAP_M = 9_800

    # get UTM bounds from dataset
    with rasterio_open(item.assets["red"].href) as src:
        bounds = Bounds(
            left=src.bounds.left,
            bottom=src.bounds.bottom + TILE_OVERLAP_M,
            right=src.bounds.right - TILE_OVERLAP_M,
            top=src.bounds.top,
        )
        print(shape(bounds).wkt)
    col, row = s2tile._zone_square_idx()
    left_source = bounds.left - col * TILE_WIDTH_M
    bottom_source = bounds.bottom - row * TILE_HEIGHT_M
    print(f"left: {left_source}")
    print(f"bottom: {bottom_source}")


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
    tile_geom = s2tile.latlon_geometry
    item_geom = shape(item.geometry)

    # item footprint can be cut off on the edges of datastrips. we need
    # to fix this before comparing geometries:
    item_utm_bounds = reproject_geometry(
        item_geom, src_crs="EPSG:4326", dst_crs=s2tile.crs
    ).bounds
    item_fixed = reproject_geometry(
        box(*item_utm_bounds), src_crs=s2tile.crs, dst_crs="EPSG:4326"
    )
    # _reverse_engineer_source(item, s2tile)
    assert item_fixed.intersects(tile_geom)
    # assert item_fixed.intersection(tile_geom).area == pytest.approx(
    #     tile_geom.area, 0.001
    # )


def test_s2_tiles_from_bounds():
    tiles = s2_tiles_from_bounds(0.72796, 47.36041, 3.68207, 50.24650)
    control_tiles = set(
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
    assert control_tiles <= set(tiles)
    1 / 0
