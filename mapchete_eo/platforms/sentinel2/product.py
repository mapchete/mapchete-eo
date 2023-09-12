from __future__ import annotations

import logging
from typing import Union

import numpy as np
import pystac
from mapchete.io.raster import ReferencedRaster, read_raster, read_raster_window
from mapchete.path import MPath
from mapchete.tile import BufferedTile
from rasterio.enums import Resampling

from mapchete_eo.io.assets import get_assets, read_mask_as_raster
from mapchete_eo.io.path import get_product_cache_path, path_in_paths
from mapchete_eo.io.profiles import COGDeflateProfile
from mapchete_eo.platforms.sentinel2.brdf import correction_grid, get_sun_zenith_angle
from mapchete_eo.platforms.sentinel2.config import BRDFConfig, CacheConfig
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import (
    ClassificationBandIndex,
    CloudType,
    L2ABand,
)
from mapchete_eo.product import EOProduct
from mapchete_eo.protocols import EOProductProtocol

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
            self.item,
            MPath.from_inp(self.config.path),
            self.config.product_path_generation_method,
        )
        self.path.makedirs()
        self._brdf_grid_cache: dict = dict()
        if self.config.brdf:
            self._brdf_bands = [
                asset_name_to_band(self.item, band) for band in self.config.brdf.bands
            ]
        else:
            self._brdf_bands = []
        self._existing_files = self.path.ls()

    def __repr__(self):
        return f"<Cache: product={self.item.id}, path={self.path}>"

    def cache_assets(self):
        # cache assets
        if self.config.assets:
            # TODO determine already existing assets
            self.item = get_assets(
                self.item,
                self.config.assets,
                self.path,
                resolution=self.config.assets_resolution.value,
                ignore_if_exists=True,
            )
            return self.item

    def cache_brdf_grids(self, metadata: S2Metadata):
        if self.config.brdf:
            resolution = self.config.brdf.resolution
            model = self.config.brdf.model

            logger.debug(
                f"prepare BRDF model '{model}' for product bands {self._brdf_bands} in {resolution} resolution"
            )
            sun_zenith_angle = None
            for band in self._brdf_bands:
                out_path = self.path / f"brdf_{model}_{band}_{resolution}.tif"
                # TODO: do check with _existing_files again to reduce S3 requests
                if not out_path.exists():
                    if sun_zenith_angle is None:
                        sun_zenith_angle = get_sun_zenith_angle(metadata)
                    grid = correction_grid(
                        metadata,
                        band,
                        sun_zenith_angle,
                        model=model,
                        resolution=resolution,
                    )
                    logger.debug(f"cache BRDF correction grid to {out_path}")
                    grid.to_file(out_path, **COGDeflateProfile(grid.meta))
                self._brdf_grid_cache[band] = out_path

    def get_brdf_grid(self, band: L2ABand):
        try:
            return self._brdf_grid_cache[band]
        except KeyError:
            if band in self._brdf_bands:
                raise KeyError(f"BRDF grid for band {band} not yet cached")
            else:
                raise KeyError(f"BRDF grid for band {band} not configured")


class S2Product(EOProduct, EOProductProtocol):
    metadata: S2Metadata
    cache: Union[Cache, None] = None

    def __init__(
        self,
        item: pystac.Item,
        metadata: Union[S2Metadata, None] = None,
        cache_config: Union[CacheConfig, None] = None,
    ):
        self.item = item
        self.metadata = metadata or S2Metadata.from_stac_item(self.item)
        self.cache = Cache(self.item, cache_config) if cache_config else None
        self.__geo_interface__ = self.metadata.__geo_interface__
        self.bounds = self.metadata.bounds
        self.crs = self.metadata.crs

    @classmethod
    def from_stac_item(
        self,
        item: pystac.Item,
        cache_config: Union[CacheConfig, None] = None,
        cache_all: bool = False,
        **kwargs,
    ) -> S2Product:
        s2product = S2Product(item, cache_config=cache_config)

        if cache_all:
            # cache assets if configured
            s2product.cache_assets()

            # cache BRDF grids if configured
            s2product.cache_brdf_grids()

        return s2product

    def __repr__(self):
        return f"<S2Product product_id={self.item.id}>"

    def cache_assets(self) -> None:
        if self.cache is not None:
            self.cache.cache_assets()

    def cache_brdf_grids(self) -> None:
        if self.cache is not None:
            self.cache.cache_brdf_grids(self.metadata)

    def read_brdf_grid(
        self,
        band: L2ABand,
        resampling: Resampling = Resampling.nearest,
        tile: Union[BufferedTile, None] = None,
        brdf_config: BRDFConfig = BRDFConfig(),
    ) -> np.ndarray:
        # read cached file if configured
        if self.cache:
            grid_path = self.cache.get_brdf_grid(band)
            return read_raster(grid_path, tile=tile, resampling=resampling).data
        # calculate on the fly
        return correction_grid(
            self.metadata,
            band,
            model=brdf_config.model,
            resolution=brdf_config.resolution,
        ).read(tile=tile, resampling=resampling)

    def read_cloud_mask(
        self,
        tile: Union[BufferedTile, None] = None,
        cloud_type: CloudType = CloudType.all,
    ) -> ReferencedRaster:
        """Return classification cloud mask."""
        return self.metadata.cloud_mask(cloud_type, dst_grid=tile)

    def read_snow_ice_mask(
        self,
        tile: Union[BufferedTile, None] = None,
    ) -> ReferencedRaster:
        """Return classification snow and ice mask."""
        return self.metadata.snow_ice_mask(dst_grid=tile)

    def read_cloud_probability_mask(
        self,
        tile: Union[BufferedTile, None] = None,
        resampling: Resampling = Resampling.bilinear,
    ) -> ReferencedRaster:
        """Return cloud probability mask."""
        return self.metadata.cloud_probability_mask(
            dst_grid=tile, resampling=resampling
        )

    def read_snow_probability_mask(
        self,
        tile: Union[BufferedTile, None] = None,
        resampling: Resampling = Resampling.bilinear,
    ) -> ReferencedRaster:
        """Return classification snow and ice mask."""
        return self.metadata.snow_probability_mask(dst_grid=tile, resampling=resampling)

    def read_scl_mask(
        self,
        tile: Union[BufferedTile, None] = None,
    ) -> ReferencedRaster:
        return read_raster(
            MPath(self.item.assets["scl"].href),
            tile=tile,
            resampling=Resampling.nearest.name,
        )


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


def asset_name_to_band(item: pystac.Item, asset_name: str) -> L2ABand:
    asset = item.assets[asset_name]
    asset_path = MPath(asset.href)
    band_name = asset_path.name.split(".")[0]
    return L2ABand[band_name]
