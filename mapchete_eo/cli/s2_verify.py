from typing import List

import click
import pystac
from mapchete.cli.options import opt_debug
from mapchete.path import MPath
from tqdm import tqdm

from mapchete_eo.cli import options_arguments
from mapchete_eo.platforms.sentinel2.config import (
    BRDFConfig,
    MaskConfig,
    SceneClassification,
)
from mapchete_eo.platforms.sentinel2.product import S2Product, asset_mpath
from mapchete_eo.platforms.sentinel2.types import L2ABand


@click.command()
@options_arguments.arg_stac_items
@options_arguments.opt_assets
@options_arguments.opt_brdf_model
@opt_debug
def s2_verify(
    stac_items: List[MPath],
    assets=None,
    asset_exists_check: bool = False,
    brdf_model=None,
    **_,
):
    """Verify Sentinel-2 products."""
    for item_path in tqdm(stac_items):
        item = pystac.Item.from_file(item_path)
        for asset in assets:
            if asset not in item.assets:
                tqdm.write(f"[ERROR] {item.id} has no asset named '{asset}")
            if asset_exists_check:
                path = asset_mpath(item=item, asset=asset)
                if not path.exists():
                    tqdm.write(
                        f"[ERROR] {item.id} asset '{asset}' with path {str(path)} does not exist"
                    )
