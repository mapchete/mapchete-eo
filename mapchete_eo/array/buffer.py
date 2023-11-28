import numpy.ma as ma
from scipy.ndimage import binary_dilation


def buffer_array(array: ma.MaskedArray, buffer: int = 0):
    if buffer == 0:
        return array

    return binary_dilation(array, iterations=buffer)
