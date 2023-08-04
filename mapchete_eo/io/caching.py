from affine import Affine
from datetime import datetime
import numpy as np
import numpy.ma as ma
from rasterio.crs import CRS
from typing import Union
import uuid

from mapchete.path import MPath
from mapchete.io import rasterio_open
from mapchete.formats.default.gtiff import DefaultGTiffProfile

from mapchete_eo.settings import DEFAULT_CACHE_LOCATION

DEFAULT_FORMATS_SPECS = {
    "GeoTIFF": DefaultGTiffProfile,
    "COG": DefaultGTiffProfile(driver="COG"),
    "GeoJSON": {},
    "FlatGeobuf": {},
}


def cache_to_file(
    in_array: np.ndarray,
    in_affine: Affine,
    in_array_dtype: str = "float32",
    nodata: Union[float, None] = 0,
    crs: Union[str, CRS] = "EPSG:4326",
    out_file_path: Union[MPath, str, None] = None,
    out_file_suffix: Union[str, None] = None,
) -> MPath:
    out_file_path = MPath.from_inp(out_file_path) if out_file_path else None
    today = datetime.now()
    temp_subpath_items = [today.year, today.month, today.day, uuid.uuid4()]

    # cache on default cache location
    if out_file_path is None:
        if out_file_suffix is None:
            raise ValueError(
                "either out_file_path or out_file_suffix has to be provided"
            )
        out_file_suffix = out_file_suffix.lstrip(".")
        out_file_path = DEFAULT_CACHE_LOCATION.joinpath(temp_subpath_items).with_suffix(
            out_file_suffix
        )

    # only directory is given
    elif not out_file_path.suffix:
        if out_file_suffix is None:
            raise ValueError(
                "either out_file_path has to be a file path or out_file_suffix has to be provided"
            )
        out_file_suffix = out_file_suffix.lstrip(".")
        today = datetime.now()
        out_file_path = out_file_path.joinpath(temp_subpath_items).with_suffix(
            out_file_suffix
        )

    # use path as is
    else:
        out_file_path = MPath.from_inp(out_file_path)

    if MPath.from_inp(out_file_path).exists():
        return out_file_path

    # Raster Workflow
    if out_file_suffix in ["tif", "tiff"]:
        profile = DEFAULT_FORMATS_SPECS["COG"].copy()
        profile.update(dtype=in_array_dtype, nodata=nodata)
        if in_array.ndim == 2:
            in_array = ma.expand_dims(in_array, 0)
        count, height, width = in_array.shape
        with rasterio_open(
            out_file_path,
            "w+",
            count=count,
            height=height,
            width=width,
            transform=in_affine,
            crs=crs,
            **profile,
            in_memory=False,
        ) as out_file:
            out_file.write(in_array)

    # TODO: Vector Workflow
    elif out_file_suffix in ["fgb", "geojson"]:
        raise NotImplementedError

    else:
        raise ValueError(f"invalid suffix given: {out_file_suffix}")

    return out_file_path
