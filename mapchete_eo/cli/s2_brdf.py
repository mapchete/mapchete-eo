from typing import List
import click
import numpy as np
import pystac
from mapchete.cli.options import opt_debug
from mapchete.io import rasterio_open
from mapchete.path import MPath

from mapchete_eo.cli import options_arguments
from mapchete_eo.io.profiles import COGDeflateProfile
from mapchete_eo.platforms.sentinel2.brdf.config import BRDFModels
from mapchete_eo.platforms.sentinel2.config import BRDFConfig
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.platforms.sentinel2.metadata_parser import Resolution
from mapchete_eo.platforms.sentinel2.types import L2ABand


@click.command()
@options_arguments.arg_stac_item
@options_arguments.opt_dst_path
@options_arguments.opt_s2_l2a_bands
@options_arguments.opt_resolution
@options_arguments.opt_brdf_model
@options_arguments.opt_dump_detector_footprints
@options_arguments.opt_brdf_detector_iter
@opt_debug
def s2_brdf(
    stac_item: MPath,
    dst_path: MPath,
    l2a_bands: List[L2ABand] = [L2ABand.B04, L2ABand.B03, L2ABand.B02],
    resolution: Resolution = Resolution["120m"],
    brdf_model: BRDFModels = BRDFModels.HLS,
    dump_detector_footprints=False,
    brdf_detector_iter: bool = False,
    **_,
):
    """Generate 8bit RGB image from Sentinel-2 product."""
    item = pystac.Item.from_file(stac_item)
    product = S2Product.from_stac_item(item)
    if not resolution.value:
        resolution = Resolution["10m"]
    grid = product.metadata.grid(resolution)
    click.echo(product)
    for band in l2a_bands:
        if dump_detector_footprints:
            out_path = (
                dst_path / stac_item.without_suffix().name
                + f"_footprints_{band.name}_{resolution}.tif"
            )
            click.echo(
                f"write detector footprint for band {band.name} to {str(out_path)}"
            )
            product.metadata.detector_footprints(band, grid).to_file(out_path)
        out_path = (
            dst_path / stac_item.without_suffix().name
            + f"_brdf_{band.name}_{resolution}.tif"
        )
        click.echo(
            f"write BRDF correction grid for band {band.name} to {str(out_path)}"
        )
        with rasterio_open(
            out_path,
            "w",
            **COGDeflateProfile(grid.to_dict(), count=1, dtype=np.float32),
        ) as dst:
            dst.write(
                product.read_brdf_grid(
                    band,
                    grid=grid,
                    brdf_config=BRDFConfig(
                        model=brdf_model,
                        resolution=resolution,
                        per_detector_correction=brdf_detector_iter,
                    ),
                ),
                1,
            )
