import numpy as np
import numpy.ma as ma
import pytest
from mapchete_eo.image_operations import dtype_scale


@pytest.mark.parametrize(
    "bands_fixture", ["test_2d_array", "test_3d_array", "test_4d_array"]
)
@pytest.mark.parametrize(
    "out_dtype, max_source, max_output, nodata",
    [
        (np.uint8, 10000.0, None, None),
        (np.uint16, 5000.0, 20000, None),
        ("uint8", 10000.0, 100, 0),
        ("uint16", 1000.0, None, 1),
    ],
)
def test_dtype_scale_parametrized(
    request, bands_fixture, out_dtype, max_source, max_output, nodata
):
    bands = request.getfixturevalue(bands_fixture)

    result = dtype_scale(
        bands,
        nodata=nodata,
        out_dtype=out_dtype,
        max_source_value=max_source,
        max_output_value=max_output,
    )

    expected_dtype = np.dtype(out_dtype)
    assert isinstance(result, ma.MaskedArray)
    assert result.shape == bands.shape
    assert result.dtype == expected_dtype

    # Mask should preserve original nodata mask
    expected_mask = np.logical_or(
        bands.mask, bands == (nodata if nodata is not None else 0)
    )
    assert np.array_equal(result.mask, expected_mask)

    # Check that all unmasked values are within [1, max_output]
    max_val = max_output if max_output is not None else np.iinfo(expected_dtype).max
    unmasked = result.data[~result.mask]
    if unmasked.size > 0:
        assert unmasked.min() >= 1
        assert unmasked.max() <= max_val
