import logging
from typing import Union

from mapchete.path import MPath
import pystac

from mapchete_eo.io.assets import get_assets
from mapchete_eo.io.path import get_product_cache_path, path_in_paths
from mapchete_eo.platforms.sentinel2.brdf import (
    BRDFConfig,
    cache_brdf_correction_grids,
)
from mapchete_eo.platforms.sentinel2.config import CacheConfig

# NOTE: it is important to import S2Metadata from base and _not_ from metadata_parser
# because of the custom path mapper guesser function!
from mapchete_eo.platforms.sentinel2.base import S2Metadata
from mapchete_eo.platforms.sentinel2.types import L2ABand


logger = logging.getLogger(__name__)


class Cache:
    item: pystac.Item
    config: CacheConfig
    path: MPath

    def __init__(self, item: pystac.Item, config: CacheConfig):
        self.item = item
        self.config = config
        # TODO: maybe move this function here
        self.path = get_product_cache_path(
            self.item, self.config.path, self.config.product_path_generation_method
        )
        self.path.makedirs()
        self._brdf_grid_cache: dict = dict()

    def __repr__(self):
        return f"<Cache: product={self.item.id}, path={self.path}>"

    def ls(self):
        return self.path.ls()

    def register_brdf_grids(self, grids: dict):
        self._brdf_grid_cache.update(grids)


class S2Product:
    item: pystac.Item
    s2_metadata: S2Metadata
    cache: Union[Cache, None] = None

    def __init__(
        self,
        item: pystac.Item,
        s2_metadata: Union[S2Metadata, None] = None,
        cache_config: Union[CacheConfig, None] = None,
    ):
        self.item = item
        self.s2_metadata = s2_metadata or S2Metadata.from_stac_item(self.item)
        self.cache = Cache(self.item, cache_config) if cache_config else None

    def cache_assets(self):
        if self.cache is None:
            raise ValueError("caching assets is only possible if cache is configured")
        # cache assets
        if self.cache.config.assets:
            self.item = get_assets(
                self.item,
                self.cache.config.assets,
                self.cache.path,
                resolution=self.cache.config.assets_resolution.value,
                ignore_if_exists=True,
            )

    def cache_brdf_grids(self):
        if self.cache is None:
            raise ValueError(
                "BRDF grid caching is only possible if cache is configured"
            )
        if self.cache.config.brdf is None:
            raise ValueError("BRDF grid caching is not configured")

        resolution = self.cache.config.brdf.resolution
        model = self.cache.config.brdf.model
        bands = self.cache.config.brdf.bands
        logger.debug(
            f"prepare BRDF model '{model}' for product bands {bands} in {resolution} resolution"
        )
        out_paths = {
            asset_name_to_band_index(self.item, band): self.cache.path
            / f"brdf_{model}_{band}_{resolution}.tif"
            for band in bands
        }
        uncached = uncached_files(existing_files=self.cache.ls(), out_paths=out_paths)
        if uncached:
            cache_brdf_correction_grids(
                s2_metadata=self.s2_metadata,
                resolution=resolution,
                model=model,
                out_paths=out_paths,
                product_id=self.item.id,
                uncached=uncached,
            )
        else:
            logger.debug("BRDF model for all bands already exists.")
        self.cache.register_brdf_grids(out_paths)

    def brdf_grid(self, config: BRDFConfig):
        raise NotImplementedError


def uncached_files(existing_files=None, out_paths=None):
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
        else:
            uncached[band_idx] = out_path
    return uncached


def asset_name_to_band_index(item: pystac.Item, asset_name: str) -> int:
    asset = item.assets[asset_name]
    asset_path = MPath(asset.href)
    band_name = asset_path.name.split(".")[0]
    return L2ABand[band_name].value
