import numpy as np
import numpy.ma as ma
import pytest

from mapchete_eo.image_operations import compositing


@pytest.mark.parametrize("bands", range(1, 5))
def test_to_rgba(bands, test_3d_array):
    out = compositing.to_rgba(test_3d_array)
    assert isinstance(out, np.ndarray)
    assert not isinstance(out, ma.masked_array)
    assert out.shape == (4, 256, 256)
    assert out.dtype == np.float16
    assert out.min() >= 0.0
    assert out.max() <= 255.0


@pytest.mark.parametrize("method", compositing.METHODS.keys())
@pytest.mark.parametrize("opacity", [0, 0.5, 1])
def test_compositing_output_array(test_3d_array, method, opacity):
    out = compositing.composite(method, test_3d_array, test_3d_array, opacity=opacity)
    assert isinstance(out, ma.masked_array)
    assert out.shape == (4, 256, 256)
    assert out.dtype == np.uint8
