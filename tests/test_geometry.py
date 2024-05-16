import pytest
from mapchete.types import Bounds
from pytest_lazyfixture import lazy_fixture
from shapely import wkt
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
        lazy_fixture("antimeridian_item5"),
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


def test_buffer_antimeridian_safe():
    geometry = wkt.loads(
        "MULTIPOLYGON (((-179.9007922830362 -20.96671450145087, -179.89560144107517 -20.967617414455813, -179.90806987842126 -20.96761869724748, -179.9007922830362 -20.96671450145087)), ((-180 -20.943177886491217, -180 -20.7734127657837, -179.78774173780687 -20.77706288786702, -179.79126327516263 -20.967606679820314, -180 -20.943177886491217)), ((179.86082360813083 -20.92720983649908, 179.85883568680532 -20.926860813217523, 179.85888328436795 -20.924579253857743, 179.84773264469558 -20.924104957228145, 179.88569078371066 -20.771447035025357, 180 -20.7734127657837, 180 -20.943177886491217, 179.8925367497856 -20.930601290149554, 179.87522606375526 -20.927564560509428, 179.86082360813083 -20.92720983649908)))"
    )
    assert buffer_antimeridian_safe(geometry, buffer_m=-500)
