import pytest
from mapchete.types import Bounds
from pytest_lazyfixture import lazy_fixture
from shapely.geometry import Polygon, shape

from mapchete_eo.geometry import (
    buffer_antimeridian_safe,
    repair_antimeridian_geometry,
    transform_to_latlon,
)


def test_transform_to_latlon_empty():
    assert transform_to_latlon(Polygon(), "EPSG:3857").is_empty


@pytest.mark.parametrize(
    "item",
    [
        lazy_fixture("antimeridian_item1"),
        lazy_fixture("antimeridian_item2"),
        lazy_fixture("antimeridian_item4"),
    ],
)
def test_item_buffer_antimeridian_footprint(item):
    fixed_footprint = repair_antimeridian_geometry(shape(item.geometry))
    buffered = buffer_antimeridian_safe(fixed_footprint, buffer_m=-500)

    # buffered should be smaller than original
    assert buffered.area < fixed_footprint.area

    # however, it should still touch the antimeridian
    bounds = Bounds.from_inp(buffered)
    assert bounds.left == -180
    assert bounds.right == 180


def test_broken_antimeridian_footprint(broken_footprint):
    assert buffer_antimeridian_safe(broken_footprint, -500)
