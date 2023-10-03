import numpy as np
import pytest
import xarray as xr
from pytest_lazyfixture import lazy_fixture

from mapchete_eo.array.convert import to_dataarray, to_dataset, to_masked_array


def test_to_dataarray_2d(test_2d_array):
    attrs = dict(foo="bar")
    xarr = to_dataarray(
        test_2d_array,
        attrs=attrs,
    )
    assert isinstance(xarr, xr.DataArray)

    assert xarr.ndim == 2

    assert len(xarr.coords) == 0

    # assert other properties
    assert xarr.dtype == np.uint8
    assert xarr.attrs.get("_FillValue") == test_2d_array.fill_value
    assert xarr.attrs.get("foo") == "bar"


def test_to_dataarray_3d(test_3d_array):
    band_axis_name = "foo"
    band_names = ["red", "green", "blue"]
    attrs = dict(foo="bar")
    xarr = to_dataarray(
        test_3d_array, band_axis_name=band_axis_name, attrs=attrs, band_names=band_names
    )
    assert isinstance(xarr, xr.DataArray)

    assert xarr.ndim == 3

    # make sure band coordinates are set properly
    assert len(xarr.coords) == 1
    assert band_axis_name in xarr.coords

    for band_name in band_names:
        assert band_name in xarr.coords[band_axis_name]

    # assert other properties
    assert xarr.dtype == np.uint8
    assert xarr.attrs.get("_FillValue") == test_3d_array.fill_value
    assert xarr.attrs.get("foo") == "bar"


def test_to_dataset_4d(test_4d_array):
    band_axis_name = "foo"
    band_names = ["red", "green", "blue"]
    slice_axis_name = "foo2"
    slice_names = [str(i) for i in range(5)]
    attrs = dict(foo="bar")
    xarr = to_dataset(
        test_4d_array,
        slice_axis_name=slice_axis_name,
        slice_names=slice_names,
        band_axis_name=band_axis_name,
        band_names=band_names,
        attrs=attrs,
    )
    assert isinstance(xarr, xr.Dataset)

    # make sure dataset has 5 data arrays
    assert len(xarr) == 5

    # make sure coordinates are set properly
    assert len(xarr.coords) == 2
    assert slice_axis_name in xarr.coords
    assert band_axis_name in xarr.coords

    for band_name in band_names:
        assert band_name in xarr.coords[band_axis_name]
    for slice_name in slice_names:
        assert slice_name in xarr.coords[slice_axis_name]

    # assert other properties
    assert xarr.attrs.get("_FillValue") == test_4d_array.fill_value
    assert xarr.attrs.get("foo") == "bar"

    # data array properties
    for variable_name in xarr:
        assert xarr[variable_name].dtype == np.uint8
        assert xarr[variable_name].attrs.get("_FillValue") == test_4d_array.fill_value


@pytest.mark.parametrize(
    "masked_array",
    [
        lazy_fixture("test_2d_array"),
        lazy_fixture("test_3d_array"),
    ],
)
def test_dataarray_to_masked_array(masked_array):
    converted = to_masked_array(to_dataarray(masked_array))
    assert converted.shape == masked_array.shape
    assert converted.dtype == masked_array.dtype


@pytest.mark.parametrize(
    "masked_array",
    [
        lazy_fixture("test_4d_array"),
    ],
)
def test_dataset_to_masked_array(masked_array):
    converted = to_masked_array(to_dataset(masked_array))
    assert converted.shape == masked_array.shape
    assert converted.dtype == masked_array.dtype
