from rasterio.crs import CRS
import uuid
from datetime import datetime

from mapchete.path import MPath
from mapchete.io import rasterio_open
from mapchete.formats.default.gtiff import DefaultGTiffProfile

from mapchete_eo.settings import DEFAULT_EOX_S3_CACHE

DEFAULT_FORMATS_SPECS = {
    "GeoTIFF": DefaultGTiffProfile,
    "COG": DefaultGTiffProfile(driver="COG"),
    "GeoJSON": {},
    "FlatGeobuf": {},
}


def cache_file(
    in_array,
    in_affine,
    in_array_dtype="float32",
    nodata=0,
    epsg=4326,
    out_file_path=None,
    out_file_suffix=None,
):
    if out_file_path is None:
        today = datetime.now()
        out_file_path = MPath(
            f"{DEFAULT_EOX_S3_CACHE}/{today.year}/{today.month}/{today.day}/{uuid.uuid4()}"
        )

    mp_out_file = MPath(out_file_path)

    # Raster Workflow
    if out_file_suffix in ["tif", "tiff"]:
        if out_file_suffix is not None:
            out_file_suffix = mp_out_file.suffix
        else:
            out_file_suffix = "tif"
            mp_out_file = MPath(f"{out_file_path}.{out_file_suffix}")

        print(mp_out_file)

        if mp_out_file.exists():
            return mp_out_file._path_str

        DEFAULT_FORMATS_SPECS["COG"].update(dtype=in_array_dtype, nodata=nodata)
        with rasterio_open(
            mp_out_file,
            "w+",
            height=in_array.shape[-2],
            width=in_array.shape[-1],
            transform=in_affine,
            crs=CRS.from_epsg(epsg),
            **DEFAULT_FORMATS_SPECS["COG"],
            count=in_array.shape[0],
            in_memory=False,
        ) as out_file:
            out_file.write(in_array)

    # TODO: Vector Workflow
    if out_file_suffix in ["fgb", "geojson"]:
        raise NotImplementedError

    return mp_out_file._path_str
