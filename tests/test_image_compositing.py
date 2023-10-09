import numpy as np
import numpy.ma as ma
import pytest

from mapchete_eo import image_compositing


@pytest.mark.parametrize("bands", range(1, 5))
def test_to_rgba(bands):
    arr = np.full((bands, 256, 256), 2, dtype=np.uint8)
    out = image_compositing.to_rgba(arr)
    assert isinstance(out, np.ndarray)
    assert not isinstance(out, ma.masked_array)
    assert out.shape == (4, 256, 256)
    assert out.dtype == np.float16
    assert out.min() >= 0.0
    assert out.max() <= 255.0


@pytest.mark.parametrize("method", image_compositing.METHODS.keys())
@pytest.mark.parametrize("opacity", [0, 0.5, 1])
def test_compositing_output_array(method, opacity):
    arr = np.full((1, 256, 256), 2, dtype=np.uint8)
    out = image_compositing.composite(method, arr, arr, opacity=opacity)
    assert isinstance(out, ma.masked_array)
    assert out.shape == (4, 256, 256)
    assert out.dtype == np.uint8
