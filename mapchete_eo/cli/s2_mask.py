import click
import numpy as np
import pystac
from mapchete.cli.options import opt_debug
from mapchete.io import rasterio_open

from mapchete_eo.cli import options_arguments
from mapchete_eo.platforms.sentinel2.config import MaskConfig, SceneClassification
from mapchete_eo.platforms.sentinel2.product import S2Product


@click.command()
@options_arguments.arg_stac_item
@options_arguments.arg_dst_path
@options_arguments.opt_resolution
@options_arguments.opt_rio_profile
@options_arguments.opt_mask_footprint
@options_arguments.opt_mask_clouds
@options_arguments.opt_mask_snow_ice
@options_arguments.opt_mask_cloud_probability_threshold
@options_arguments.opt_mask_snow_probability_threshold
@options_arguments.opt_mask_scl_classes
@opt_debug
def s2_mask(
    stac_item,
    dst_path,
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
    """Generate mask for Sentinel-2 product from metadata."""
    item = pystac.Item.from_file(stac_item)
    product = S2Product.from_stac_item(item)
    grid = product.metadata.grid(resolution)
    click.echo(product)
    mask_config = MaskConfig(
        footprint=mask_footprint,
        l1c_clouds=mask_clouds,
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
        dst_path,
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
