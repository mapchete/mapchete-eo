from typing import Optional

import click
import tqdm
from mapchete.path import MPath

from mapchete_eo.platforms.sentinel2.brdf.models import BRDFModels
from mapchete_eo.io.profiles import rio_profiles
from mapchete_eo.platforms.sentinel2.archives import KnownArchives
from mapchete_eo.platforms.sentinel2.config import SceneClassification
from mapchete_eo.platforms.sentinel2.types import L2ABand, Resolution
from mapchete_eo.time import to_datetime


class TqdmUpTo(tqdm.tqdm):
    """Provides `update_to(n)` which uses `tqdm.update(delta_n)`."""

    def update_to(self, n: int = 1, nsize: int = 1, total: Optional[int] = None):
        """
        n  : int, optional
            Number of blocks transferred so far [default: 1].
        nsize  : int, optional
            Size of each block (in tqdm units) [default: 1].
        total  : int, optional
            Total size (in tqdm units). If [default: None] remains unchanged.
        """
        if total is not None:
            self.total = total
        return self.update(n * nsize - self.n)  # also sets self.n = b * bsize


def _str_to_list(_, __, value):
    if value:
        return value.split(",")
    return []


def _str_to_resolution(_, __, value):
    if value:
        return Resolution[value]


def _str_to_rio_profile(_, __, value):
    if value:
        return rio_profiles[value]


def _brdf_model_str_to_brdf(_, __, value):
    if value:
        if value == "none":
            return None
        else:
            return BRDFModels[value]


def _str_to_l2a_bands(_, __, value):
    if value:
        return [L2ABand[v] for v in value.split(",")]


def _archive_name_to_archive_cls(_, __, value):
    if value:
        return KnownArchives[value]


def _str_to_datetime(_, param, value):
    if value:
        return to_datetime(value)
    else:
        raise ValueError(f"--{param.name} is mandatory")


arg_stac_item = click.argument("stac-item", type=click.Path(path_type=MPath))
arg_stac_items = click.argument(
    "stac-items", type=click.Path(path_type=MPath), nargs=-1
)
arg_dst_path = click.argument("dst-path", type=click.Path(path_type=MPath))
opt_dst_path = click.option(
    "--dst-path", type=click.Path(path_type=MPath), default=".", show_default=True
)
opt_thumbnail_dir = click.option(
    "--thumbnail-dir", type=click.Path(path_type=MPath), default=None, show_default=True
)
opt_blacklist = click.option(
    "--blacklist",
    type=click.Path(path_type=MPath),
    default="s3://eox-mhub-cache/blacklist.txt",
    show_default=True,
)
opt_s2_l2a_bands = click.option(
    "--l2a-bands",
    type=click.STRING,
    callback=_str_to_l2a_bands,
    help=f"List of L2A bands to be used. (Available bands: {','.join([band.name for band in L2ABand])})",
    show_default=True,
    default="B04,B03,B02",
)
opt_assets_rgb = click.option(
    "--assets",
    "-a",
    type=click.STRING,
    nargs=3,
    default=["red", "green", "blue"],
    show_default=True,
)
opt_resolution = click.option(
    "--resolution",
    type=click.Choice(list(Resolution.__members__.keys())),
    default="original",
    show_default=True,
    callback=_str_to_resolution,
    help="Resample assets to this resolution in meter.",
)
opt_rio_profile = click.option(
    "--rio-profile",
    type=click.Choice(list(rio_profiles.keys())),
    default="cog_deflate",
    callback=_str_to_rio_profile,
    help="Available rasterio profiles for raster assets.",
)
opt_mask_footprint = click.option(
    "--mask-footprint", is_flag=True, help="Mask by product footprint."
)
opt_mask_clouds = click.option("--mask-clouds", is_flag=True, help="Mask out clouds.")
opt_mask_snow_ice = click.option(
    "--mask-snow-ice", is_flag=True, help="Mask out snow and ice."
)
opt_mask_cloud_probability_threshold = click.option(
    "--mask-cloud-probability-threshold",
    type=click.INT,
    default=100,
    help="Mask out pixels with cloud probability over value.",
    show_default=True,
)
opt_mask_snow_probability_threshold = click.option(
    "--mask-snow-probability-threshold",
    type=click.INT,
    default=100,
    help="Mask out pixels with snow probability over value.",
    show_default=True,
)
opt_mask_scl_classes = click.option(
    "--mask-scl-classes",
    type=click.STRING,
    callback=_str_to_list,
    help=f"Available classes: {', '.join([scene_class.name for scene_class in SceneClassification])}",
)
opt_brdf_model = click.option(
    "--brdf-model",
    type=click.Choice([model.name for model in BRDFModels]),
    default=BRDFModels.HLS,
    callback=_brdf_model_str_to_brdf,
    show_default=True,
    help="BRDF model.",
)
opt_brdf_weight = click.option(
    "--brdf-weight",
    type=click.FLOAT,
    default=1.0,
    show_default=True,
    help="BRDF model weight.",
)
opt_mgrs_tile = click.option("--mgrs-tile", type=click.STRING)
opt_start_time = click.option(
    "--start-time", type=click.STRING, callback=_str_to_datetime, help="Start time"
)
opt_end_time = click.option(
    "--end-time", type=click.STRING, callback=_str_to_datetime, help="End time"
)
opt_archive = click.option(
    "--archive",
    type=click.Choice([archive.name for archive in KnownArchives]),
    default="S2AWS_COG",
    help="Archive to read from.",
    callback=_archive_name_to_archive_cls,
)
opt_collection = click.option(
    "--collection",
    type=click.STRING,
    help="Data collection to be queried.",
)
opt_endpoint = click.option(
    "--endpoint",
    type=click.STRING,
    help="Search endpoint.",
)
opt_catalog_json = click.option(
    "--catalog-json",
    type=click.Path(path_type=MPath),
    help="JSON file for a static catalog.",
)
opt_name = click.option("--name", type=click.STRING, help="Static catalog name.")
opt_description = click.option(
    "--description", type=click.STRING, help="Static catalog description."
)
opt_assets = click.option(
    "--assets",
    type=click.STRING,
    callback=_str_to_list,
    help="STAC item assets.",
)
opt_assets_dst_resolution = click.option(
    "--assets-dst-resolution",
    type=click.Choice(list(Resolution.__members__.keys())),
    default="original",
    show_default=True,
    callback=_str_to_resolution,
    help="Resample assets to this resolution in meter.",
)
opt_assets_dst_rio_profile = click.option(
    "--assets-dst-rio-profile",
    type=click.Choice(list(rio_profiles.keys())),
    default="cog_deflate",
    callback=_str_to_rio_profile,
    help="Available rasterio profiles for raster assets.",
)
opt_copy_metadata = click.option(
    "--copy-metadata", is_flag=True, help="Download granule metadata and QI bands."
)
opt_overwrite = click.option(
    "--overwrite", "-o", is_flag=True, help="Overwrite existing files."
)
opt_dump_detector_footprints = click.option(
    "--dump-detector-footprints",
    is_flag=True,
    help="Also dump products detector footprints.",
)

opt_out_dtype = click.option(
    "--out-dtype", default="uint8", help="Out dType string; default: uint8"
)

opt_brdf_log10 = click.option(
    "--brdf-log10",
    is_flag=True,
    help="Flag to switch BRDF input band convertion to log10. Default: False",
)

opt_brdf_detector_iter = click.option(
    "--brdf-detector-iter",
    is_flag=True,
    help="Switch to switch if the brdf correction should be iterated over the detector footprints or merge them prefering higher angle value. Default: False",
)
