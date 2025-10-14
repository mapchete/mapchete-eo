import pytest

from mapchete_eo.io import products_to_slices
from mapchete_eo.product import EOProduct
from mapchete_eo.sort import TargetDateSort, CloudCoverSort


@pytest.mark.parametrize("sort_by", ["date", "cloud_cover"])
@pytest.mark.parametrize("reverse", [True, False])
def test_sort(s2_stac_items, sort_by, reverse):
    if sort_by == "date":
        sort_method = TargetDateSort(target_date="1970-01-01", reverse=reverse)
        sort_property = "datetime"
    elif sort_by == "cloud_cover":
        sort_method = CloudCoverSort(reverse=reverse)
        sort_property = "eo:cloud_cover"
    slices = products_to_slices(
        [EOProduct.from_stac_item(item) for item in s2_stac_items],
        group_by_property="id",
        sort=sort_method,
    )
    assert slices
    sorted_properties = [slice_.get_property(sort_property) for slice_ in slices]
    assert sorted_properties == sorted(sorted_properties, reverse=reverse)
