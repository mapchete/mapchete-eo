"""This module includes functions to check if variable types match expected formats."""

import numpy as np


def assert_image_format(image, fcn_name: str, arg_name: str, force_alpha: bool = True):
    """Assert if image arguments have the expected format.

    Checks:
        - Image is a numpy array
        - Array is of floating-point type
        - Array is 3D (height x width x channels)
        - Array has the correct number of layers (3 or 4)

    Args:
        image: The image to be checked.
        fcn_name (str): Calling function name for display in error messages.
        arg_name (str): Relevant argument name for display in error messages.
        force_alpha (bool): Whether the image must include an alpha layer.

    Raises:
        TypeError: If type or shape are incorrect.
    """
    if not isinstance(image, np.ndarray):
        raise TypeError(
            f"\n[Invalid Type]\n"
            f"Function: {fcn_name}\n"
            f"Argument: {arg_name}\n"
            f"Expected: numpy.ndarray\n"
            f"Got: {type(image).__name__}\n"
            f'Hint: Pass a numpy.ndarray for "{arg_name}".'
        )

    if image.dtype.kind != "f":
        raise TypeError(
            f"\n[Invalid Data Type]\n"
            f"Function: {fcn_name}\n"
            f"Argument: {arg_name}\n"
            f'Expected dtype kind: "f" (floating-point)\n'
            f'Got dtype kind: "{image.dtype.kind}"\n'
            f"Hint: Convert the array to float, e.g., image.astype(float)."
        )

    if len(image.shape) != 3:
        raise TypeError(
            f"\n[Invalid Dimensions]\n"
            f"Function: {fcn_name}\n"
            f"Argument: {arg_name}\n"
            f"Expected: 3D array (height x width x channels)\n"
            f"Got: {len(image.shape)}D array\n"
            f"Hint: Ensure the array has three dimensions."
        )

    if force_alpha and image.shape[2] != 4:
        raise TypeError(
            f"\n[Invalid Channel Count]\n"
            f"Function: {fcn_name}\n"
            f"Argument: {arg_name}\n"
            f"Expected: 4 layers (R, G, B, Alpha)\n"
            f"Got: {image.shape[2]} layers\n"
            f"Hint: Include all four channels if force_alpha=True."
        )


def assert_opacity(opacity, fcn_name: str, arg_name: str = "opacity"):
    """Assert if opacity has the expected format.

    Checks:
        - Opacity is float or int
        - Opacity is within 0.0 <= x <= 1.0

    Args:
        opacity: The opacity value to be checked.
        fcn_name (str): Calling function name for display in error messages.
        arg_name (str): Argument name for display in error messages.

    Raises:
        TypeError: If type is not float or int.
        ValueError: If opacity is out of range.
    """
    if not isinstance(opacity, (float, int)):
        raise TypeError(
            f"\n[Invalid Type]\n"
            f"Function: {fcn_name}\n"
            f"Argument: {arg_name}\n"
            f"Expected: float (or int)\n"
            f"Got: {type(opacity).__name__}\n"
            f"Hint: Pass a float between 0.0 and 1.0."
        )

    if not 0.0 <= opacity <= 1.0:
        raise ValueError(
            f"\n[Out of Range]\n"
            f"Function: {fcn_name}\n"
            f"Argument: {arg_name}\n"
            f"Expected: value in range 0.0 <= x <= 1.0\n"
            f"Got: {opacity}\n"
            f"Hint: Clamp or normalize the value to the valid range."
        )
