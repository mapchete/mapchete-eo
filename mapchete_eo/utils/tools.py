from fsspec.exceptions import FSTimeoutError
import hashlib
import logging
import numpy as np
import numpy.ma as ma
from rasterio import Affine, CRS
from rasterio.enums import Resampling
from rasterio.warp import reproject
from retry import retry
import xml.etree.ElementTree as etree

from mapchete.path import MPath
from mapchete.io import rasterio_open

from mapchete_eo.utils.time import str_to_date
from mapchete_eo.exceptions import (
    CorruptedGTiffError,
)
from mapchete_eo.settings import MP_EO_IO_RETRY_SETTINGS

logger = logging.getLogger(__name__)


@retry(
    logger=logger,
    exceptions=(TimeoutError, FSTimeoutError),
    **MP_EO_IO_RETRY_SETTINGS,
)
def open_xml(path: MPath):
    logger.debug(f"open {path}")
    return etree.fromstring(path.read_text())


def get_product_cache_path(product=None, config=None, bbox=None, postfix=""):
    """
    Create product path with high cardinality prefixes optimized for S3.

    product_path_generation option:

    "product_id":
    <cache_basepath>/<product-id>

    "product_hash":
    <cache_basepath>/<product-hash>

    "d/m/yyyy":
    <cache_basepath>/<product-day>/<product-month>/<product-year>/<product-id>

    "yyyy/m/d":
    <cache_basepath>/<product-year>/<product-month>/<product-day>/<product-id>
    """
    product_path_generation = config["cache"]["product_path_generation"]
    mp_cache_path = MPath(
        config["cache"]["path"],
    )
    if product_path_generation == "product_id":
        return mp_cache_path.joinpath(product["id"] + postfix)
    elif product_path_generation == "product_hash":
        return mp_cache_path.joinpath(
            hashlib.md5(f"{product['id']}".encode()).hexdigest(),
            product["id"] + postfix,
        )

    elif product_path_generation == "d/m/yyyy":
        timestamp = str_to_date(product["properties"]["timestamp"])
        return mp_cache_path.joinpath(
            str(timestamp.day),
            str(timestamp.month),
            str(timestamp.year),
            product["id"] + postfix,
        )
    elif product_path_generation == "yyyy/m/d":
        timestamp = str_to_date(product["properties"]["timestamp"])
        return mp_cache_path.joinpath(
            str(timestamp.year),
            str(timestamp.month),
            str(timestamp.day),
            product["id"] + postfix,
        )
    else:
        raise ValueError(
            f"invalid product_path_generation option: {product_path_generation}"
        )


def _uncached_files(existing_files=None, out_paths=None, remove_invalid=False):
    """
    Check if paths provided in out_paths exist in existing_files.

    Parameters
    ----------
    existing_files : list
        List of existing files
    out_paths : dict
        Mapping of {foo: out_path} for files to check
    remove_invalid : bool
        Validate existing raster files and remove them if required.

    Returns
    -------
    Subset of out_paths for files which currently do not exist.
    """
    if isinstance(out_paths, str):
        out_paths = {None: out_paths}
    uncached = {}
    for band_idx, out_path in out_paths.items():
        if path_in_paths(out_path, existing_files):
            logger.debug("%s already cached", out_path)
            if remove_invalid:
                try:
                    _validate_raster(out_path, remove_corrupt_file=True)
                except CorruptedGTiffError:
                    uncached[band_idx] = out_path
        else:
            uncached[band_idx] = out_path
    return uncached


def _validate_raster(out_path, assert_crs_authority=True, remove_corrupt_file=False):
    try:
        with rasterio_open(out_path) as src:
            if not isinstance(src.crs, CRS):
                raise TypeError(
                    f"{out_path} does not have a valid CRS: {type(src.crs)}"
                )
            elif assert_crs_authority and src.crs.to_authority() is None:
                raise ValueError(
                    f"{out_path} CRS cannot be converted to authority: {src.crs.to_wkt()}"
                )
            elif not isinstance(src.transform, Affine):
                raise TypeError(
                    f"{out_path} does not have a valid transform object: {type(src.transform)}"
                )
            else:
                logger.debug(
                    f"{out_path} CRS and transform look ok: {src.crs}, {src.transform}"
                )
    except Exception as exc:
        logger.error("%s corrupt: %s", out_path, str(exc))
        if remove_corrupt_file:
            logger.debug("removing %s ...", out_path)
            MPath(out_path).rm()
        raise CorruptedGTiffError(f"{out_path} is invalid: {str(exc)}") from exc


def path_in_paths(path, existing_paths):
    if path.startswith("s3://"):
        return path.lstrip("s3://") in existing_paths
    else:
        for existing_path in existing_paths:
            if existing_path.endswith(path):
                return True
        else:
            return False


def _resample_array(
    in_array=None,
    in_transform=None,
    in_crs=None,
    nodata=0,
    dst_transform=None,
    dst_crs=None,
    dst_shape=None,
    resampling="bilinear",
):
    dst_data = np.empty(dst_shape, in_array.dtype)
    reproject(
        in_array,
        dst_data,
        src_transform=in_transform,
        src_crs=in_crs,
        src_nodata=nodata,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        dst_nodata=nodata,
        resampling=Resampling[resampling],
    )
    return ma.masked_array(
        data=np.nan_to_num(dst_data, nan=nodata),
        mask=ma.masked_invalid(dst_data).mask,
        fill_value=nodata,
    )
