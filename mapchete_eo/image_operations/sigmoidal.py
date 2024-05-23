import numpy as np
from numpy.typing import DTypeLike

# The type to be used for all intermediate math
# operations. Should be a float because values will
# be scaled to the range 0..1 for all work.

math_type = np.float16

epsilon = float(np.finfo(math_type).eps)


def sigmoidal(
    arr: np.ndarray,
    contrast: int,
    bias: float,
    out_dtype: DTypeLike = np.float16,
):
    """
    Taken from rio-color (consult sevcikp for changes)

    Sigmoidal contrast is type of contrast control that
    adjusts the contrast without saturating highlights or shadows.
    It allows control over two factors:
    the contrast range from light to dark, and where the middle value
    of the mid-tones falls. The result is a non-linear and smooth
    contrast change.

    Parameters
    ----------
    arr : ndarray, float, 0 .. 1
        Array of color values to adjust
    contrast : integer
        Enhances the intensity differences between the lighter and darker
        elements of the image. For example, 0 is none, 3 is typical and
        20 is a lot.
    bias : float, between 0 and 1
        Threshold level for the contrast function to center on
        (typically centered at 0.5)

    Notes
    ----------

    Sigmoidal contrast is based on the sigmoidal transfer function:

    .. math:: g(u) = ( 1/(1 + e^{- \alpha * u + \beta)})

    This sigmoid function is scaled so that the output is bound by
    the interval [0, 1].

    .. math:: ( 1/(1 + e^(\beta * (\alpha - u))) - 1/(1 + e^(\beta * \alpha)))/
        ( 1/(1 + e^(\beta*(\alpha - 1))) - 1/(1 + e^(\beta * \alpha)) )

    Where :math: `\alpha` is the threshold level, and :math: `\beta` the
    contrast factor to be applied.

    References
    ----------
    .. [CT] Hany Farid "Fundamentals of Image Processing"
            http://www.cs.dartmouth.edu/farid/downloads/tutorials/fip.pdf

    """
    if isinstance(out_dtype, str):
        out_dtype = np.dtype(getattr(np, out_dtype))
    if not isinstance(out_dtype, np.dtype):
        raise TypeError(
            f"Harmonization dtype needs to be valid numpy dtype is: {type(out_dtype)}"
        )

    if (arr.max() > 1.0 + epsilon) or (arr.min() < 0 - epsilon):
        raise ValueError("Input array must have float values between 0 and 1")

    if (bias > 1.0 + epsilon) or (bias < 0 - epsilon):
        raise ValueError("bias must be a scalar float between 0 and 1")

    alpha, beta = bias, contrast
    # We use the names a and b to match documentation.

    if alpha == 0.0:
        alpha = epsilon

    if beta == 0.0:
        return arr.astype(out_dtype, copy=False)

    np.seterr(divide="ignore", invalid="ignore")
    if beta > 0:
        numerator = 1 / (1 + np.exp(beta * (alpha - arr))) - 1 / (
            1 + np.exp(beta * alpha)
        )
        denominator = 1 / (1 + np.exp(beta * (alpha - 1))) - 1 / (
            1 + np.exp(beta * alpha)
        )
        return (numerator / denominator).astype(out_dtype, copy=False)

    else:
        # Inverse sigmoidal function:
        # todo: account for 0s
        return (
            (
                (beta * alpha)
                - np.log(
                    (
                        1
                        / (
                            (arr / (1 + np.exp(beta * alpha - beta)))
                            - (arr / (1 + np.exp(beta * alpha)))
                            + (1 / (1 + np.exp(beta * alpha)))
                        )
                    )
                    - 1
                )
            )
            / beta
        ).astype(out_dtype, copy=False)
