import numpy as np
import numpy.ma as ma
import pytest

from mapchete_eo.image_operations.fillnodata import FillSelectionMethod, fillnodata


@pytest.mark.parametrize("method", list(FillSelectionMethod))
@pytest.mark.parametrize("smoothing_iterations", [0, 3])
def test_fillnodata(test_3d_array, method, smoothing_iterations):
    out = fillnodata(
        test_3d_array, method=method, smoothing_iterations=smoothing_iterations
    )
    assert isinstance(out, ma.MaskedArray)
    assert out.shape == (3, 256, 256)
    assert out.dtype == np.uint8
    assert out.mask.sum() < test_3d_array.mask.sum()
