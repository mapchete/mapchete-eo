from typing import List

import click
import numpy as np
from numpy.typing import DTypeLike
import pystac
from mapchete.cli.options import opt_debug
from mapchete.io import rasterio_open
from mapchete.path import MPath
from mapchete import Timer

from mapchete_eo.cli import options_arguments
from mapchete_eo.image_operations import linear_normalization
from mapchete_eo.platforms.sentinel2.config import (
    BRDFConfig,
    MaskConfig,
    SceneClassification,
)
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.platforms.sentinel2.types import Resolution


@click.command()
@options_arguments.arg_stac_item
@options_arguments.opt_dst_path
@options_arguments.opt_assets_rgb
@options_arguments.opt_resolution
@options_arguments.opt_rio_profile
@options_arguments.opt_mask_footprint
@options_arguments.opt_mask_snow_ice
@options_arguments.opt_mask_cloud_probability_threshold
@options_arguments.opt_mask_snow_probability_threshold
@options_arguments.opt_mask_scl_classes
@options_arguments.opt_brdf_model
@options_arguments.opt_brdf_weight
@options_arguments.opt_brdf_log10
@options_arguments.opt_brdf_detector_iter
@options_arguments.opt_out_dtype
@opt_debug
def s2_rgb(
    stac_item: MPath,
    dst_path: MPath,
    assets: List[str] = ["red", "green", "blue"],
    resolution: Resolution = Resolution["120m"],
    rio_profile=None,
    mask_footprint=False,
    mask_snow_ice=False,
    mask_cloud_probability_threshold=100,
    mask_snow_probability_threshold=100,
    mask_scl_classes=None,
    brdf_model=None,
    brdf_weight: float = 1.0,
    brdf_log10: bool = False,
    brdf_detector_iter: bool = False,
    out_dtype: DTypeLike = "uint8",
    **_,
):
    """Generate 8bit RGB image from Sentinel-2 product."""
    out_dtype = np.dtype(out_dtype)

    if not dst_path.suffix:
        dst_path = dst_path / stac_item.without_suffix().name + ".tif"
    if resolution == Resolution.original:
        resolution = Resolution["10m"]
    product = S2Product.from_stac_item(pystac.Item.from_file(stac_item))
    grid = product.metadata.grid(resolution)
    click.echo(
        f"writing {stac_item} assets {', '.join(assets)} to {dst_path} in {resolution.name} resolution"
    )
    with Timer() as t:
        mask_config = MaskConfig(
            footprint=mask_footprint,
            snow_ice=mask_snow_ice,
            cloud_probability_threshold=mask_cloud_probability_threshold,
            snow_probability_threshold=mask_snow_probability_threshold,
            scl_classes=(
                [SceneClassification[scene_class] for scene_class in mask_scl_classes]
                if bool(mask_scl_classes)
                else None
            ),
        )
        rgb = product.read_np_array(
            assets=assets,
            grid=grid,
            mask_config=mask_config,
            brdf_config=BRDFConfig(
                bands=assets,
                model=brdf_model,
                correction_weight=brdf_weight,
                log10_bands_scale=brdf_log10,
                per_detector_correction=brdf_detector_iter,
            )
            if brdf_model
            else None,
        )
        with rasterio_open(
            dst_path,
            mode="w",
            crs=grid.crs,
            transform=grid.transform,
            width=grid.width,
            height=grid.height,
            dtype=out_dtype,
            count=len(assets),
            nodata=0,
            **rio_profile,
        ) as dst:
            if out_dtype == np.uint8:
                dst.write(linear_normalization(rgb, out_min=1))
            else:
                dst.write(rgb)
    click.echo(
        f"{stac_item} assets {', '.join(assets)} to {dst_path} in {resolution.name} written in {t}"
    )
