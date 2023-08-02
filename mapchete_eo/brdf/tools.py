import logging
import math
import numpy as np
from affine import Affine
import xml.etree.ElementTree as etree

from mapchete.io.raster import resample_from_array

logger = logging.getLogger(__name__)


def get_constant_sun_angle(min_lat=None, max_lat=None, **kwargs):
    """
    Calculate constant sun angle between latitudes.

    Returns
    =======
    sun angle in radians : float
    """
    central_lat = min_lat + (max_lat - min_lat) / 2
    return math.radians(_sun_angle(central_lat))


def get_sun_angle_array(min_lat=None, max_lat=None, shape=None):
    """
    Calculate array of sun angles between latitudes.

    Returns
    =======
    sun angle array in radians : np.ndarray
    """
    # return get_constant_sun_angle(min_lat, max_lat)
    height, width = shape
    cell_size = (max_lat - min_lat) / (height + 1)

    # move by half a pixel so pixel centers are represented
    top = max_lat - cell_size / 2

    # generate one column of angles
    angles = [_sun_angle(top - i * cell_size) for i in range(width)]

    # expand column to output shape width
    return np.radians(
        np.array([[i for _ in range(width)] for i in angles], dtype=np.float32)
    )


def _sun_angle(lat):
    """
    Calculate the constant sun zenith angle via 6th polynomial function see HLS.

    See page 13 of:
    https://hls.gsfc.nasa.gov/wp-content/uploads/2019/01/HLS.v1.4.UserGuide_draft_ver3.1.pdf
    """
    # constants used for sun angle calculation
    # See page 13 of:
    # https://hls.gsfc.nasa.gov/wp-content/uploads/2019/01/HLS.v1.4.UserGuide_draft_ver3.1.pdf
    k0 = 31
    k1 = -0.127
    k2 = 0.0119
    k3 = 2.4e-05
    k4 = -9.48e-07
    k5 = -1.95e-09
    k6 = 6.15e-11

    # Constant sun zenith angle 6th polynomial function
    return (
        k0
        + k1 * lat
        + k2 * (lat**2)
        + k4 * (lat**4)
        + k3 * (lat**3)
        + k5 * (lat**5)
        + k6 * (lat**6)
    )


# Resample array with upper left corner coords, cell size and crs to target tile
def get_angle_tile(
    in_arr_crs,
    in_angle_arr,
    left,
    top,
    grid_x_size,
    grid_y_size,
    out_tile,
    nodata=-32768,
    resampling="cubic_spline",
):
    in_affine = Affine(grid_x_size, 0, left, 0, -grid_y_size, top)

    angle_tile = np.squeeze(
        resample_from_array(
            in_raster=in_angle_arr.astype(np.float32),
            in_affine=in_affine,
            out_tile=out_tile,
            in_crs=in_arr_crs,
            resampling=resampling,
            nodataval=nodata,
        )
    )
    if angle_tile.shape[-1] != out_tile.shape[-1]:
        raise RuntimeError
    return angle_tile


def get_view_azimuth_arr(angles_file, band):
    angle_tree = etree.parse(angles_file)
    angle_root = angle_tree.getroot()

    view_azimuth = None
    idx = 0
    for angle_group in angle_root.iter("Viewing_Incidence_Angles_Grids"):
        if int(angle_group.get("bandId")) != band:
            continue
        for angles in angle_group.findall("Azimuth"):
            for values in angles.findall("Values_List"):
                for i, value in zip(range(len(values)), values):
                    arr_row = np.expand_dims(np.array(value.text.split(" ")), axis=0)
                    arr_row = np.where(arr_row == "NaN", 0, arr_row).astype(np.float32)
                    if view_azimuth is None:
                        view_azimuth = arr_row
                    else:
                        if idx == 0:
                            view_azimuth = np.append(view_azimuth, arr_row, axis=0)
                        if arr_row.shape[1] != view_azimuth[i].shape[0]:
                            raise TypeError
                        if idx != 0:
                            view_azimuth[i] = np.where(
                                view_azimuth[i] != 0, view_azimuth[i], arr_row
                            )
        idx += 1
    return view_azimuth


def get_view_zenith_arr(angles_file, band):
    angle_tree = etree.parse(angles_file)
    angle_root = angle_tree.getroot()

    view_zenith = None
    idx = 0
    for angle_group in angle_root.iter("Viewing_Incidence_Angles_Grids"):
        if int(angle_group.get("bandId")) != band:
            continue
        for angles in angle_group.findall("Zenith"):
            for values in angles.findall("Values_List"):
                for i, value in zip(range(len(values)), values):
                    arr_row = np.expand_dims(np.array(value.text.split(" ")), axis=0)
                    arr_row = np.where(arr_row == "NaN", 0, arr_row).astype(np.float32)
                    if view_zenith is None:
                        view_zenith = arr_row
                    else:
                        if idx == 0:
                            view_zenith = np.append(view_zenith, arr_row, axis=0)
                        if arr_row.shape[1] != view_zenith[i].shape[0]:
                            raise TypeError
                        if idx != 0:
                            view_zenith[i] = np.where(
                                view_zenith[i] != 0, view_zenith[i], arr_row
                            )
        idx += 1
    return view_zenith


def get_sun_zenith_arr(angles_file):
    angle_tree = etree.parse(angles_file)
    angle_root = angle_tree.getroot()

    sun_zenith = None
    for angle_group in angle_root.iter("Sun_Angles_Grid"):
        for angles in angle_group.findall("Zenith"):
            for values in angles.findall("Values_List"):
                for value in values:
                    arr_row = np.expand_dims(np.array(value.text.split(" ")), axis=0)
                    if sun_zenith is None:
                        sun_zenith = arr_row
                    else:
                        sun_zenith = np.append(sun_zenith, arr_row, axis=0)
    return sun_zenith


def get_sun_azimuth_arr(angles_file):
    angle_tree = etree.parse(angles_file)
    angle_root = angle_tree.getroot()

    sun_azimuth = None
    for angle_group in angle_root.iter("Sun_Angles_Grid"):
        for angles in angle_group.findall("Azimuth"):
            for values in angles.findall("Values_List"):
                for value in values:
                    arr_row = np.expand_dims(np.array(value.text.split(" ")), axis=0)
                    if sun_azimuth is None:
                        sun_azimuth = arr_row
                    else:
                        sun_azimuth = np.append(sun_azimuth, arr_row, axis=0)
    return sun_azimuth


# Get sun zenith for modis
def get_norm_sun_zenith(lat_list):
    if len(lat_list) != 5:
        raise ValueError
    get_norm_sun_zenith = 0
    k_list = [
        31,
        -0.127,
        0.0119,
        2.4 * pow(10, -5),
        -9.48 * pow(10, -7),
        -1.95 * pow(10, -9),
        6.15 * pow(10, -11),
    ]

    # 6th polynomial of center latitude with Landsat 8 polynomian constants
    for k, lat in zip(k_list, lat_list):
        if k == 31:
            get_norm_sun_zenith += k
        else:
            get_norm_sun_zenith += k * lat
    return get_norm_sun_zenith
