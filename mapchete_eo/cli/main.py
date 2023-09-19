from typing import Union

import click
import numpy as np
import pystac
import tqdm
from mapchete.cli.options import opt_bounds, opt_debug
from mapchete.io import rasterio_open

from mapchete_eo.image_operations import linear_normalization
from mapchete_eo.io.profiles import rio_profiles
from mapchete_eo.platforms.sentinel2 import S2Metadata
from mapchete_eo.platforms.sentinel2.config import (
    AWSL2ACOGv1,
    MaskConfig,
    SceneClassification,
)
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.platforms.sentinel2.types import Resolution
from mapchete_eo.search import STACSearchCatalog, STACStaticCatalog


class TqdmUpTo(tqdm.tqdm):
    """Provides `update_to(n)` which uses `tqdm.update(delta_n)`."""

    def update_to(self, n: int = 1, nsize: int = 1, total: Union[int, None] = None):
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


def _str_to_resolution(_, __, value):
    if value:
        return Resolution[value]


def _str_to_rio_profile(_, __, value):
    if value:
        return rio_profiles[value]


arg_stac_item = click.argument("stac-item", type=click.Path())
arg_dst = click.argument("dst", type=click.Path())
opt_assets = click.option(
    "--assets", "-a", type=click.STRING, nargs=3, default=["red", "green", "blue"]
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
opt_mask_footprint = click.option("--mask-footprint", is_flag=True)
opt_mask_clouds = click.option("--mask-clouds", is_flag=True)
opt_mask_snow_ice = click.option("--mask-snow-ice", is_flag=True)
opt_mask_cloud_probability_threshold = click.option(
    "--mask-cloud-probability-threshold", type=click.INT, default=100
)
opt_mask_snow_probability_threshold = click.option(
    "--mask-snow-probability-threshold", type=click.INT, default=100
)
opt_mask_scl_classes = click.option(
    "--mask-scl-classes",
    type=click.STRING,
    callback=_str_to_list,
    help=f"Available classes: {', '.join([scene_class.name for scene_class in SceneClassification])}",
)


@click.group(help="Tools around mapchete EO package.")
@click.pass_context
def eo(ctx):
    ctx.ensure_object(dict)


@eo.command()
@click.pass_context
@click.argument("dst_path", type=click.Path())
@opt_bounds
@click.option("--mgrs-tile", type=click.STRING)
@click.option("--start-time", type=click.STRING, help="Start time")
@click.option("--end-time", type=click.STRING, help="End time")
@click.option(
    "--archive",
    type=click.Choice(["sentinel-s2-l2a-cogs"]),
    default="sentinel-s2-l2a-cogs",
    help="Archive to read from.",
)
@click.option(
    "--collection",
    type=click.STRING,
    help="Data collection to be queried.",
)
@click.option(
    "--endpoint",
    type=click.STRING,
    help="Search endpoint.",
)
@click.option(
    "--catalog-json",
    type=click.STRING,
    help="JSON file for a static catalog.",
)
@click.option("--name", type=click.STRING, help="Static catalog name.")
@click.option("--description", type=click.STRING, help="Static catalog description.")
@click.option(
    "--assets",
    type=click.STRING,
    callback=_str_to_list,
    help="Also copy/convert assets to catalog.",
)
@click.option(
    "--assets-dst-resolution",
    type=click.Choice(list(Resolution.__members__.keys())),
    default="original",
    show_default=True,
    callback=_str_to_resolution,
    help="Resample assets to this resolution in meter.",
)
@click.option(
    "--assets-dst-rio-profile",
    type=click.Choice(list(rio_profiles.keys())),
    default="cog_deflate",
    callback=_str_to_rio_profile,
    help="Available rasterio profiles for raster assets.",
)
@click.option(
    "--copy-metadata", is_flag=True, help="Download granule metadata and QI bands."
)
@click.option("--overwrite", "-o", is_flag=True, help="Overwrite existing files.")
@opt_debug
def static_catalog(
    ctx,
    dst_path,
    bounds=None,
    mgrs_tile=None,
    start_time=None,
    end_time=None,
    archive=None,
    collection=None,
    endpoint=None,
    catalog_json=None,
    name=None,
    description=None,
    assets=None,
    assets_dst_resolution=None,
    assets_dst_rio_profile=None,
    copy_metadata=False,
    overwrite=False,
    **kwargs,
):
    selector = {
        "archive": archive,
        "catalog-json": catalog_json,
        "endpoint": endpoint,
    }
    if len([v for v in selector.values() if v is not None]) != 1:
        raise click.ClickException(
            "exactly one of --archive, --catalog-json or --endpoint has to be set."
        )
    if any([start_time is None, end_time is None]):
        raise click.ClickException("--start-time and --end-time are mandatory")
    if all([bounds is None, mgrs_tile is None]):
        raise click.ClickException("--bounds and --mgrs-tile are required")

    if archive:
        if archive == "sentinel-s2-l2a-cogs":
            catalog = AWSL2ACOGv1(
                bounds=bounds,
                start_time=start_time,
                end_time=end_time,
                mgrs_tile=mgrs_tile,
            ).catalog
        else:
            raise ValueError(
                "currently ony archive 'sentinel-s2-l2a-cogs' is supported"
            )
    if catalog_json:
        catalog = STACStaticCatalog(
            baseurl=catalog_json,
            bounds=bounds,
            start_time=start_time,
            end_time=end_time,
        )
    if endpoint:
        catalog = STACSearchCatalog(
            baseurl=endpoint,
            bounds=bounds,
            start_time=start_time,
            end_time=end_time,
        )

    with TqdmUpTo(
        unit="products", unit_scale=True, miniters=1, disable=opt_debug
    ) as progress:
        catalog_json = catalog.write_static_catalog(
            dst_path,
            name=name,
            description=description,
            assets=assets,
            assets_dst_resolution=assets_dst_resolution.value,
            assets_convert_profile=assets_dst_rio_profile,
            copy_metadata=copy_metadata,
            metadata_parser_classes=(S2Metadata,),
            overwrite=overwrite,
            progress_callback=progress.update_to,
        )

    click.echo(f"Catalog successfully written to {catalog_json}")


@eo.command()
@arg_stac_item
@arg_dst
@opt_assets
@opt_resolution
@opt_rio_profile
@opt_mask_footprint
@opt_mask_clouds
@opt_mask_snow_ice
@opt_mask_cloud_probability_threshold
@opt_mask_snow_probability_threshold
@opt_mask_scl_classes
@opt_debug
def s2_rgb(
    stac_item,
    dst,
    assets=None,
    resolution=None,
    rio_profile=None,
    mask_footprint=False,
    mask_clouds=False,
    mask_snow_ice=False,
    mask_cloud_probability_threshold=100,
    mask_snow_probability_threshold=100,
    mask_scl_classes=None,
    **_,
):
    item = pystac.Item.from_file(stac_item)
    product = S2Product.from_stac_item(item)
    grid = product.metadata.grid(resolution)
    click.echo(product)
    mask_config = MaskConfig(
        footprint=mask_footprint,
        cloud=mask_clouds,
        snow_ice=mask_snow_ice,
        cloud_probability=mask_cloud_probability_threshold != 100,
        cloud_probability_threshold=mask_cloud_probability_threshold,
        snow_probability=mask_snow_probability_threshold != 100,
        snow_probability_threshold=mask_snow_probability_threshold,
        scl=bool(mask_scl_classes),
        scl_classes=[
            SceneClassification[scene_class] for scene_class in mask_scl_classes
        ]
        if bool(mask_scl_classes)
        else None,
    )
    rgb = product.read_np_array(assets=assets, grid=grid, mask_config=mask_config)
    with rasterio_open(
        dst,
        mode="w",
        crs=grid.crs,
        transform=grid.transform,
        width=grid.width,
        height=grid.height,
        dtype=np.uint8,
        count=len(assets),
        nodata=0,
        **rio_profile,
    ) as dst:
        dst.write(linear_normalization(rgb))


@eo.command()
@arg_stac_item
@arg_dst
@opt_resolution
@opt_rio_profile
@opt_mask_footprint
@opt_mask_clouds
@opt_mask_snow_ice
@opt_mask_cloud_probability_threshold
@opt_mask_snow_probability_threshold
@opt_mask_scl_classes
@opt_debug
def s2_mask(
    stac_item,
    dst,
    resolution=None,
    rio_profile=None,
    mask_footprint=False,
    mask_clouds=False,
    mask_snow_ice=False,
    mask_cloud_probability_threshold=100,
    mask_snow_probability_threshold=100,
    mask_scl_classes=None,
    **_,
):
    item = pystac.Item.from_file(stac_item)
    product = S2Product.from_stac_item(item)
    grid = product.metadata.grid(resolution)
    click.echo(product)
    mask_config = MaskConfig(
        footprint=mask_footprint,
        cloud=mask_clouds,
        snow_ice=mask_snow_ice,
        cloud_probability=mask_cloud_probability_threshold != 100,
        cloud_probability_threshold=mask_cloud_probability_threshold,
        snow_probability=mask_snow_probability_threshold != 100,
        snow_probability_threshold=mask_snow_probability_threshold,
        scl=bool(mask_scl_classes),
        scl_classes=[
            SceneClassification[scene_class] for scene_class in mask_scl_classes
        ]
        if bool(mask_scl_classes)
        else None,
    )
    mask = product.get_mask(mask_config=mask_config).data
    rgb = np.stack([mask * 255, mask, mask])
    with rasterio_open(
        dst,
        mode="w",
        crs=grid.crs,
        transform=grid.transform,
        width=grid.width,
        height=grid.height,
        dtype=np.uint8,
        count=3,
        nodata=0,
        **rio_profile,
    ) as dst:
        dst.write(rgb)
