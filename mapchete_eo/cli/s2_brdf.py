import click
import numpy as np
import pystac
from mapchete.cli.options import opt_debug
from mapchete.io import rasterio_open

from mapchete_eo.cli import options_arguments
from mapchete_eo.io.profiles import COGDeflateProfile
from mapchete_eo.platforms.sentinel2.config import BRDFConfig
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.platforms.sentinel2.metadata_parser import Resolution


@click.command()
@options_arguments.arg_stac_item
@options_arguments.arg_dst_path
@options_arguments.opt_s2_l2a_bands
@options_arguments.opt_resolution
@options_arguments.opt_brdf_model
@options_arguments.opt_dump_detector_footprints
@options_arguments.opt_brdf_weight
@options_arguments.opt_brdf_detector_iter
@opt_debug
def s2_brdf(
    stac_item,
    dst_path,
    l2a_bands=None,
    resolution=None,
    brdf_model=None,
    dump_detector_footprints=False,
    brdf_weight: float = 1.0,
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
            out_path = dst_path / f"detector_footprints_{band.name}_resolution.tif"
            click.echo(
                f"write detector footprint for band {band.name} to {str(out_path)}"
            )
            product.metadata.detector_footprints(band, grid).to_file(out_path)
        out_path = dst_path / f"brdf_{brdf_model}_{band.name}_{resolution}.tif"
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
                        correction_weight=brdf_weight,
                        brdf_as_detector_iter_flag=brdf_detector_iter,
                    ),
                ),
                1,
            )
