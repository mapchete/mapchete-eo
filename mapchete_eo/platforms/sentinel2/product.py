from __future__ import annotations

import logging
from typing import List, Union

import numpy as np
import numpy.ma as ma
import pystac
from mapchete.io.raster import ReferencedRaster, read_raster
from mapchete.io.vector import reproject_geometry
from mapchete.path import MPath
from mapchete.tile import BufferedTile
from mapchete.types import Bounds
from rasterio.enums import Resampling
from rasterio.features import rasterize
from shapely.geometry import shape

from mapchete_eo.exceptions import AllMasked, EmptyProductException
from mapchete_eo.io.assets import get_assets, read_mask_as_raster
from mapchete_eo.io.path import get_product_cache_path
from mapchete_eo.io.profiles import COGDeflateProfile
from mapchete_eo.platforms.sentinel2.brdf import correction_grid, get_sun_zenith_angle
from mapchete_eo.platforms.sentinel2.config import BRDFConfig, CacheConfig, MaskConfig
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import (
    CloudType,
    L2ABand,
    Resolution,
    SceneClassification,
)
from mapchete_eo.product import EOProduct
from mapchete_eo.protocols import EOProductProtocol, GridProtocol
from mapchete_eo.settings import DEFAULT_CATALOG_CRS
from mapchete_eo.types import Grid, NodataVals

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
        self.id = self.item.id

        self.metadata = metadata or S2Metadata.from_stac_item(self.item)
        self.cache = Cache(self.item, cache_config) if cache_config else None

        self.__geo_interface__ = self.item.geometry
        self.bounds = Bounds.from_inp(shape(self))
        self.crs = DEFAULT_CATALOG_CRS

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

    def read_np_array(
        self,
        assets: Union[List[str], None] = None,
        eo_bands: Union[List[str], None] = None,
        tile: BufferedTile = None,
        resampling: Resampling = Resampling.nearest,
        nodatavals: NodataVals = None,
        mask_config: MaskConfig = MaskConfig(),
        **kwargs,
    ) -> ma.MaskedArray:
        mask = self.get_mask(tile, mask_config).data
        if mask.all():
            raise EmptyProductException(f"{self} is empty over {tile}")
        arr = super().read_np_array(
            assets=assets,
            eo_bands=eo_bands,
            tile=tile,
            resampling=resampling,
            nodatavals=nodatavals,
        )
        # bring mask to same shape as data array
        arr.mask = np.repeat(np.expand_dims(mask, axis=0), arr.shape[0], axis=0)
        return arr

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
        logger.debug("read classification cloud mask for %s", str(self))
        return self.metadata.cloud_mask(cloud_type, dst_grid=tile)

    def read_snow_ice_mask(
        self,
        tile: Union[BufferedTile, None] = None,
    ) -> ReferencedRaster:
        """Return classification snow and ice mask."""
        logger.debug("read classification snow and ice mask for %s", str(self))
        return self.metadata.snow_ice_mask(dst_grid=tile)

    def read_cloud_probability(
        self,
        tile: Union[BufferedTile, None] = None,
        resampling: Resampling = Resampling.bilinear,
    ) -> ReferencedRaster:
        """Return cloud probability mask."""
        logger.debug("read cloud probability mask for %s", str(self))
        return self.metadata.cloud_probability(dst_grid=tile, resampling=resampling)

    def read_snow_probability(
        self,
        tile: Union[BufferedTile, None] = None,
        resampling: Resampling = Resampling.bilinear,
    ) -> ReferencedRaster:
        """Return classification snow and ice mask."""
        logger.debug("read snow probability mask for %s", str(self))
        return self.metadata.snow_probability(dst_grid=tile, resampling=resampling)

    def read_scl(
        self,
        grid: Union[GridProtocol, Resolution] = Resolution["20m"],
    ) -> ReferencedRaster:
        """Return SCL mask."""
        logger.debug("read SCL mask for %s", str(self))
        grid = (
            self.metadata.grid(grid)
            if isinstance(grid, Resolution)
            else Grid.from_obj(grid)
        )
        return read_mask_as_raster(
            MPath(self.item.assets["scl"].href),
            dst_grid=grid,
            resampling=Resampling.nearest,
            masked=True,
        )

    def footprint_nodata_mask(
        self,
        grid: Union[GridProtocol, Resolution] = Resolution["10m"],
    ) -> ReferencedRaster:
        """Return rasterized footprint mask."""
        grid = (
            self.metadata.grid(grid)
            if isinstance(grid, Resolution)
            else Grid.from_obj(grid)
        )
        return ReferencedRaster(
            rasterize(
                [reproject_geometry(self, self.crs, grid.crs)],
                out_shape=grid.shape,
                transform=grid.transform,
                all_touched=True,
                fill=1,
                default_value=0,
            ).astype(bool),
            transform=grid.transform,
            bounds=grid.bounds,
            crs=grid.crs,
        )

    def get_mask(
        self,
        grid: Union[GridProtocol, Resolution] = Resolution["10m"],
        mask_config: MaskConfig = MaskConfig(),
    ) -> ReferencedRaster:
        """Merge masks into one 2D array."""
        grid = (
            self.metadata.grid(grid)
            if isinstance(grid, Resolution)
            else Grid.from_obj(grid)
        )

        def _check_full(arr):
            if arr.all():
                raise AllMasked()

        out = np.zeros(shape=grid.shape, dtype=bool)
        try:
            _check_full(out)
            if mask_config.footprint:
                out += self.footprint_nodata_mask(grid).data
                _check_full(out)
            if mask_config.cloud:
                out += self.read_cloud_mask(grid, mask_config.cloud_type).data
                _check_full(out)
            if mask_config.cloud_probability:
                cld_prb = self.read_cloud_probability(grid).data
                out += np.where(
                    cld_prb >= mask_config.cloud_probability_threshold, True, False
                )
                _check_full(out)
            if mask_config.scl:
                scl_arr = self.read_scl(grid).data
                # convert SCL classes to pixel values
                scl_values = [scl.value for scl in mask_config.scl_classes or []]
                # mask out specific pixel values
                out += np.isin(scl_arr, scl_values)
                _check_full(out)
            if mask_config.snow_ice:
                out += self.read_snow_ice_mask(grid).data
                _check_full(out)
            if mask_config.snow_probability:
                snw_prb = self.read_snow_probability(grid).data
                out += np.where(
                    snw_prb >= mask_config.snow_probability_threshold, True, False
                )
                _check_full(out)
        except AllMasked:
            logger.debug(
                "mask for product %s already full, skip reading other masks", self.id
            )

        return ReferencedRaster(out, grid.transform, grid.bounds, grid.crs)


def asset_name_to_band(item: pystac.Item, asset_name: str) -> L2ABand:
    asset = item.assets[asset_name]
    asset_path = MPath(asset.href)
    band_name = asset_path.name.split(".")[0]
    return L2ABand[band_name]
