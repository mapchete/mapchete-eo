import numpy as np
import numpy.ma as ma
import pytest
from rasterio.dtypes import dtype_ranges
from mapchete_eo.image_operations import linear_normalization


@pytest.mark.parametrize(
    "out_dtype", [np.uint8, "uint8", np.uint16, "uint16", np.float32, "float32"]
)
@pytest.mark.parametrize("use_out_min", [True, False])
def test_linear_normalization_parametrized(test_3d_array, out_dtype, use_out_min):
    """
    Parametrized test for linear_normalization using test_3d_array.
    Covers different dtypes and optional out_min.
    """
    bands = test_3d_array.copy()
    bands_minmax = [(0, 255), (0, 255), (0, 255)]
    out_min_val = 5 if use_out_min else None

    result = linear_normalization(
        bands,
        bands_minmax_values=bands_minmax,
        out_dtype=out_dtype,
        out_min=out_min_val,
    )

    # type and shape checks
    assert isinstance(result, ma.MaskedArray)
    assert result.shape == bands.shape

    # dtype resolution
    expected_dtype = np.dtype(out_dtype)
    assert result.dtype == expected_dtype

    # mask should be preserved
    assert np.array_equal(result.mask, bands.mask)

    # output values within expected range
    min_val = (
        out_min_val if out_min_val is not None else dtype_ranges[str(expected_dtype)][0]
    )
    max_val = dtype_ranges[str(expected_dtype)][1]
    assert result.data.min() >= min_val
    assert result.data.max() <= max_val


def test_linear_normalization_band_length_mismatch(test_3d_array):
    """Test ValueError when bands and bands_minmax_values lengths mismatch."""
    bands_minmax = [(0, 150), (10, 160)]  # only 2 instead of 3
    with pytest.raises(
        ValueError, match="bands and bands_minmax_values must have the same length"
    ):
        linear_normalization(test_3d_array, bands_minmax_values=bands_minmax)


def test_linear_normalization_invalid_dtype(test_3d_array):
    """Test KeyError when an invalid out_dtype is provided."""
    bands_minmax = [(0, 150), (10, 160), (20, 170)]
    with pytest.raises(KeyError, match="invalid out_dtype"):
        linear_normalization(
            test_3d_array, bands_minmax_values=bands_minmax, out_dtype="invalid_dtype"
        )
