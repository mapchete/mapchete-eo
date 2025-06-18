import numpy as np
import numpy.ma as ma
import pytest

from mapchete_eo.image_operations.sigmoidal import sigmoidal


@pytest.mark.parametrize("contrast", [0, 2, 20])
@pytest.mark.parametrize("bias", [0, 0.25, 0.45])
def test_sigmodial_output_array(test_3d_array, contrast, bias, output_dtype="float32"):
    out = sigmoidal(test_3d_array / 255, contrast, bias, output_dtype)
    assert isinstance(out, ma.masked_array)
    assert out.shape == (3, 256, 256)
    assert out.dtype == np.float32
