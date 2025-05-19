from __future__ import annotations

import logging
from typing import Dict, List, Optional, Union

import numpy as np
import numpy.ma as ma
import pystac
from mapchete.io.raster import ReferencedRaster, read_raster_window, resample_from_array
from mapchete.geometry import reproject_geometry
from mapchete.path import MPath
from mapchete.protocols import GridProtocol
from mapchete.types import Bounds, Grid, NodataVals
from rasterio.enums import Resampling
from rasterio.features import rasterize
from shapely.geometry import shape


from mapchete_eo.array.buffer import buffer_array
from mapchete_eo.platforms.sentinel2.brdf.config import BRDFModels
from mapchete_eo.platforms.sentinel2.brdf.correction import apply_correction
from mapchete_eo.exceptions import (
    AllMasked,
    AssetError,
    BRDFError,
    CorruptedProduct,
    EmptyFootprintException,
    EmptyProductException,
)
from mapchete_eo.geometry import buffer_antimeridian_safe
from mapchete_eo.io.assets import get_assets, read_mask_as_raster
from mapchete_eo.io.path import asset_mpath, get_product_cache_path
from mapchete_eo.io.profiles import COGDeflateProfile
from mapchete_eo.platforms.sentinel2.brdf import correction_values
from mapchete_eo.platforms.sentinel2.bandpass_adjustment import (
    apply_bandpass_adjustment,
)
from mapchete_eo.platforms.sentinel2.config import (
    BRDFConfig,
    BRDFModelConfig,
    CacheConfig,
    MaskConfig,
)
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.types import (
    CloudType,
    L2ABand,
    ProductQIMaskResolution,
    Resolution,
)
from mapchete_eo.product import EOProduct, add_to_blacklist
from mapchete_eo.protocols import EOProductProtocol
from mapchete_eo.settings import mapchete_eo_settings

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
                asset_name_to_l2a_band(self.item, band)
                for band in self.config.brdf.bands
            ]
        else:
            self._brdf_bands = []
        try:
            self._existing_files = self.path.ls()
        except FileNotFoundError:
            self._existing_files = None

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
                item_href_in_dst_dir=False,
            )
            return self.item

    def cache_brdf_grids(self, metadata: S2Metadata):
        if self.config.brdf:
            resolution = self.config.brdf.resolution
            model = self.config.brdf.model

            logger.debug(
                f"prepare BRDF model '{model}' for product bands {self._brdf_bands} in {resolution} resolution"
            )
            for band in self._brdf_bands:
                out_path = self.path / f"brdf_{model}_{band.name}_{resolution}.tif"
                # TODO: do check with _existing_files again to reduce S3 requests
                if not out_path.exists():
                    try:
                        grid = correction_values(
                            metadata,
                            band,
                            model=model,
                            resolution=resolution,
                            per_detector=self.config.brdf.per_detector_correction,
                        )
                    except BRDFError as exc:
                        error_msg = (
                            f"product {self.item.get_self_href()} is corrupted: {exc}"
                        )
                        logger.error(error_msg)
                        add_to_blacklist(self.item.get_self_href())
                        raise CorruptedProduct(error_msg)

                    logger.debug("cache BRDF correction grid to %s", out_path)
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
    item_dict: dict
    cache: Optional[Cache] = None
    _scl_cache: Dict[GridProtocol, np.ndarray]

    def __init__(
        self,
        item: pystac.Item,
        metadata: Optional[S2Metadata] = None,
        cache_config: Optional[CacheConfig] = None,
    ):
        self.item_dict = item.to_dict()
        self.id = item.id

        self._metadata = metadata
        self._scl_cache = dict()
        self.cache = Cache(item, cache_config) if cache_config else None

        self.__geo_interface__ = item.geometry
        self.bounds = Bounds.from_inp(shape(self))
        self.crs = mapchete_eo_settings.default_catalog_crs

    @classmethod
    def from_stac_item(
        self,
        item: pystac.Item,
        cache_config: Optional[CacheConfig] = None,
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

    @property
    def metadata(self) -> S2Metadata:
        if not self._metadata:
            self._metadata = S2Metadata.from_stac_item(
                pystac.Item.from_dict(self.item_dict)
            )
        return self._metadata

    def __repr__(self):
        return f"<S2Product product_id={self.id}>"

    def clear_cached_data(self):
        logger.debug("clear S2Product caches")
        if self._metadata is not None:
            self._metadata.clear_cached_data()
            self._metadata = None
        self._scl_cache = dict()

    def read_np_array(
        self,
        assets: Optional[List[str]] = None,
        eo_bands: Optional[List[str]] = None,
        grid: Union[GridProtocol, Resolution] = Resolution["10m"],
        resampling: Resampling = Resampling.nearest,
        nodatavals: NodataVals = None,
        raise_empty: bool = True,
        apply_offset: bool = True,
        apply_scale: bool = False,
        apply_sentinel2_bandpass_adjustment: bool = False,
        mask_config: MaskConfig = MaskConfig(),
        brdf_config: Optional[BRDFConfig] = None,
        fill_value: int = 0,
        target_mask: Optional[np.ndarray] = None,
        **kwargs,
    ) -> ma.MaskedArray:
        assets = assets or []
        eo_bands = eo_bands or []
        apply_offset = apply_offset and not self.metadata.boa_offset_applied
        if eo_bands:
            count = len(eo_bands)
            raise NotImplementedError("please use asset names for now")
        else:
            count = len(assets)
        if isinstance(grid, Resolution):
            grid = self.metadata.grid(grid)
        mask = self.get_mask(grid, mask_config, target_mask=target_mask).data
        if nodatavals is None:
            nodatavals = fill_value
        elif fill_value is None and nodatavals is not None:
            fill_value = nodatavals
        if mask.all():
            if raise_empty:
                raise EmptyProductException(
                    f"{self}: configured mask over {grid} covers everything"
                )
            else:
                return self.empty_array(count, grid=grid, fill_value=fill_value)

        arr = super().read_np_array(
            assets=assets,
            eo_bands=eo_bands,
            grid=grid,
            resampling=resampling,
            raise_empty=False,
            apply_offset=apply_offset,
            apply_scale=apply_scale,
        )

        # bring mask to same shape as data array
        expanded_mask = np.repeat(np.expand_dims(mask, axis=0), arr.shape[0], axis=0)
        arr.set_fill_value(fill_value)
        arr[expanded_mask] = fill_value
        arr[expanded_mask] = ma.masked

        if arr.mask.all():
            if raise_empty:
                raise EmptyProductException(
                    f"{self}: is empty over {grid} after reading bands and applying all masks"
                )
            else:
                return self.empty_array(count, grid=grid, fill_value=fill_value)

        # apply Sentinel-2 bandpass adjustment
        if apply_sentinel2_bandpass_adjustment:
            arr = self._apply_sentinel2_bandpass_adjustment(
                uncorrected=arr, assets=assets
            )

        # apply BRDF config if required
        if brdf_config:
            arr = self._apply_brdf(
                uncorrected=arr,
                assets=assets,
                brdf_config=brdf_config,
                grid=grid,
                resampling=resampling,
                mask_config=mask_config,
            )

        return ma.MaskedArray(arr, fill_value=fill_value)

    def cache_assets(self) -> None:
        if self.cache is not None:
            self.cache.cache_assets()

    def cache_brdf_grids(self) -> None:
        if self.cache is not None:
            self.cache.cache_brdf_grids(self.metadata)

    def read_brdf_grid(
        self,
        band: L2ABand,
        resampling: Resampling = Resampling.bilinear,
        grid: Union[GridProtocol, Resolution] = Resolution["20m"],
        brdf_config: BRDFModelConfig = BRDFConfig(),
    ) -> np.ndarray:
        grid = (
            self.metadata.grid(grid)
            if isinstance(grid, Resolution)
            else Grid.from_obj(grid)
        )
        try:
            # read cached file if configured
            if self.cache:
                return read_raster_window(
                    self.cache.get_brdf_grid(band),
                    grid=grid,
                    resampling=resampling,
                )
            # calculate on the fly
            return resample_from_array(
                correction_values(
                    self.metadata,
                    band,
                    model=brdf_config.model,
                    resolution=brdf_config.resolution,
                    footprints_cached_read=brdf_config.footprints_cached_read,
                    per_detector=brdf_config.per_detector_correction,
                ),
                out_grid=grid,
                resampling=resampling,
                keep_2d=True,
            )
        except (AssetError, BRDFError) as exc:
            error_msg = f"product {self.item.get_self_href()} is corrupted: {exc}"
            logger.error(error_msg)
            add_to_blacklist(self.item.get_self_href())
            raise CorruptedProduct(error_msg)

    def read_l1c_cloud_mask(
        self,
        grid: Union[GridProtocol, Resolution] = Resolution["20m"],
        cloud_type: CloudType = CloudType.all,
        cached_read: bool = False,
    ) -> ReferencedRaster:
        """Return classification cloud mask."""
        logger.debug("read classification cloud mask for %s", str(self))
        return self.metadata.l1c_cloud_mask(
            cloud_type, dst_grid=grid, cached_read=cached_read
        )

    def read_snow_ice_mask(
        self,
        grid: Union[GridProtocol, Resolution] = Resolution["20m"],
        cached_read: bool = False,
    ) -> ReferencedRaster:
        """Return classification snow and ice mask."""
        logger.debug("read classification snow and ice mask for %s", str(self))
        return self.metadata.snow_ice_mask(dst_grid=grid, cached_read=cached_read)

    def read_cloud_probability(
        self,
        grid: Union[GridProtocol, Resolution] = Resolution["20m"],
        resampling: Resampling = Resampling.bilinear,
        from_resolution: ProductQIMaskResolution = ProductQIMaskResolution["20m"],
        cached_read: bool = False,
    ) -> ReferencedRaster:
        """Return cloud probability mask."""
        logger.debug("read cloud probability mask for %s", str(self))
        return self.metadata.cloud_probability(
            dst_grid=grid,
            resampling=resampling,
            from_resolution=from_resolution,
            cached_read=cached_read,
        )

    def read_snow_probability(
        self,
        grid: Union[GridProtocol, Resolution] = Resolution["20m"],
        resampling: Resampling = Resampling.bilinear,
        from_resolution: ProductQIMaskResolution = ProductQIMaskResolution["20m"],
        cached_read: bool = False,
    ) -> ReferencedRaster:
        """Return classification snow and ice mask."""
        logger.debug("read snow probability mask for %s", str(self))
        return self.metadata.snow_probability(
            dst_grid=grid,
            resampling=resampling,
            from_resolution=from_resolution,
            cached_read=cached_read,
        )

    def read_scl(
        self,
        grid: Union[GridProtocol, Resolution] = Resolution["20m"],
        cached_read: bool = False,
    ) -> ReferencedRaster:
        """Return SCL mask."""
        grid = (
            self.metadata.grid(grid)
            if isinstance(grid, Resolution)
            else Grid.from_obj(grid)
        )
        grid_hash = hash((grid.transform, grid.shape))
        if grid_hash not in self._scl_cache:
            logger.debug("read SCL mask for %s", str(self))
            self._scl_cache[grid_hash] = read_mask_as_raster(
                asset_mpath(self.item, "scl"),
                dst_grid=grid,
                resampling=Resampling.nearest,
                masked=True,
                cached_read=cached_read,
            )
        return self._scl_cache[grid_hash]

    def footprint_nodata_mask(
        self,
        grid: Union[GridProtocol, Resolution] = Resolution["10m"],
        buffer_m: float = 0,
    ) -> ReferencedRaster:
        """Return rasterized footprint mask."""
        grid = (
            self.metadata.grid(grid)
            if isinstance(grid, Resolution)
            else Grid.from_obj(grid)
        )
        if buffer_m:
            footprint = buffer_antimeridian_safe(shape(self), buffer_m=buffer_m)
            if footprint.is_empty:
                raise EmptyFootprintException(
                    f"buffer value of {buffer_m} results in an empty geometry for footprint {shape(self).wkt}"
                )
        else:
            footprint = shape(self)

        return ReferencedRaster(
            rasterize(
                [
                    reproject_geometry(
                        footprint,
                        self.crs,
                        grid.crs,
                        # CRS Bounds are sometimes smaller than (Mapchete) Grid Bounds,
                        # if clipping allowed it will mask out features at CRS Bounds border,
                        # therefore clip_to_crs_bounds: False; see mapchete.geometry.reproject reproject_geometry
                        clip_to_crs_bounds=False,
                    )
                ],
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
        target_mask: Optional[np.ndarray] = None,
    ) -> ReferencedRaster:
        """Merge masks into one 2D array."""
        grid = (
            self.metadata.grid(grid)
            if isinstance(grid, Resolution)
            else Grid.from_obj(grid)
        )

        if target_mask is None:
            target_mask = np.zeros(shape=grid.shape, dtype=bool)
        else:
            if target_mask.shape != grid.shape:
                raise ValueError("a target mask must have the same shape as the grid")
            logger.debug("got custom target mask to start with: %s", target_mask)

        def _check_full(arr):
            # ATTENTION: target_mask and out have to be combined *after* mask was buffered!
            # use 'logical or' not '+' !!!
            if (arr | target_mask).all():
                raise AllMasked()

        out = np.zeros(shape=grid.shape, dtype=bool)
        logger.debug("generate mask for product %s ...", str(self))
        try:
            _check_full(out)
            if mask_config.footprint:
                logger.debug("generate footprint nodata mask ...")
                try:
                    out |= self.footprint_nodata_mask(
                        grid, buffer_m=mask_config.footprint_buffer_m
                    ).data
                    _check_full(out)
                except EmptyFootprintException:
                    raise AllMasked()
            if mask_config.l1c_cloud_type:
                logger.debug("generate L1C mask ...")
                out |= self.read_l1c_cloud_mask(
                    grid,
                    mask_config.l1c_cloud_type,
                    cached_read=mask_config.l1c_cloud_mask_cached_read,
                ).data
                _check_full(out)
            if mask_config.cloud_probability_threshold != 100:
                logger.debug(
                    "generate cloud probability (%s) mask ...",
                    mask_config.cloud_probability_threshold,
                )
                cld_prb = self.read_cloud_probability(
                    grid,
                    from_resolution=mask_config.cloud_probability_resolution,
                    cached_read=mask_config.cloud_probability_cached_read,
                ).data
                out |= np.where(
                    cld_prb >= mask_config.cloud_probability_threshold, True, False
                )
                _check_full(out)
            if mask_config.scl_classes:
                logger.debug(
                    "generate SCL mask using %s ...",
                    ", ".join(
                        [scl_class.name for scl_class in mask_config.scl_classes]
                    ),
                )
                # convert SCL classes to pixel values
                scl_values = [scl.value for scl in mask_config.scl_classes]
                # read SCL mask
                scl_arr = self.read_scl(
                    grid, cached_read=mask_config.scl_cached_read
                ).data
                # mask out specific pixel values
                out |= np.isin(scl_arr, scl_values)
                _check_full(out)
            if mask_config.snow_ice:
                logger.debug("generate snow & ice mask ...")
                out |= self.read_snow_ice_mask(
                    grid, cached_read=mask_config.snow_ice_mask_cached_read
                ).data
                _check_full(out)
            if mask_config.snow_probability_threshold != 100:
                logger.debug(
                    "generate snow probability (%s) mask ...",
                    mask_config.snow_probability_threshold,
                )
                snw_prb = self.read_snow_probability(
                    grid,
                    from_resolution=mask_config.snow_probability_resolution,
                    cached_read=mask_config.snow_probability_cached_read,
                ).data
                out |= np.where(
                    snw_prb >= mask_config.snow_probability_threshold, True, False
                )
                _check_full(out)
            if mask_config.buffer:
                logger.debug(
                    "apply buffer (%s) to combined mask ...", mask_config.buffer
                )
                out = buffer_array(array=out, buffer=mask_config.buffer)
                _check_full(out)
        except AllMasked:
            logger.debug(
                "mask for product %s already full, skip reading other masks", self.id
            )

        # ATTENTION: target_mask and out have to be combined *after* mask was buffered!
        # use 'logical or' not '+' !!!
        return ReferencedRaster(
            out | target_mask,
            transform=grid.transform,
            crs=grid.crs,
            bounds=grid.bounds,
        )

    def _apply_sentinel2_bandpass_adjustment(
        self, uncorrected: ma.MaskedArray, assets: List[str], computing_dtype=np.float32
    ) -> ma.MaskedArray:
        out_arr: ma.MaskedArray = ma.masked_array(
            data=np.zeros(uncorrected.shape, uncorrected.dtype),
            mask=uncorrected.mask.copy(),
            fill_value=uncorrected.fill_value,
        )
        for band_idx, asset in enumerate(assets):
            out_arr[band_idx] = apply_bandpass_adjustment(
                uncorrected[band_idx],
                item=self.item,
                l2a_band=asset_name_to_l2a_band(self.item, asset),
                computing_dtype=computing_dtype,
                out_dtype=uncorrected.dtype,
            )
        return out_arr

    def _apply_brdf(
        self,
        uncorrected: ma.MaskedArray,
        assets: List[str],
        brdf_config: BRDFConfig,
        grid: Union[GridProtocol, Resolution, None] = Resolution["10m"],
        resampling: Resampling = Resampling.nearest,
        mask_config: MaskConfig = MaskConfig(),
    ) -> ma.MaskedArray:
        out_arr: ma.MaskedArray = ma.masked_array(
            data=np.zeros(uncorrected.shape, uncorrected.dtype),
            mask=uncorrected.mask.copy(),
            fill_value=uncorrected.fill_value,
        )

        # apply default correction defined in root
        if brdf_config.model == BRDFModels.none:
            logger.debug("no default BRDF model specified")
            out_arr[:] = uncorrected
        else:
            logger.debug("applying %s to bands", brdf_config.model)
            for band_idx, asset in enumerate(assets):
                out_arr[band_idx] = apply_correction(
                    band=uncorrected[band_idx],
                    correction=self.read_brdf_grid(
                        asset_name_to_l2a_band(self.item, asset),
                        resampling=resampling,
                        grid=grid,
                        brdf_config=brdf_config,
                    ),
                    correction_weight=brdf_config.correction_weight,
                    log10_bands_scale=brdf_config.log10_bands_scale,
                )

        # if SCL-specific correction is configured, apply and overwrite values in array
        if brdf_config.scl_specific_configurations:
            logger.debug("SCL class specific BRDF correction required")
            scl_arr = self.read_scl(grid, mask_config.scl_cached_read).data

            for scl_config in brdf_config.scl_specific_configurations:
                scl_mask = np.isin(
                    scl_arr, [scl_class.value for scl_class in scl_config.scl_classes]
                )

                for band_idx, asset in enumerate(assets):
                    if scl_config.model == BRDFModels.none:
                        # use uncorrected values from original array
                        out_arr[band_idx][scl_mask] = uncorrected[band_idx][scl_mask]

                    elif scl_mask.any():
                        logger.debug(
                            "applying BRDF model %s to SCL classes %s",
                            scl_config.model.value,
                            ", ".join(
                                [scl_class.name for scl_class in scl_config.scl_classes]
                            ),
                        )
                        # apply correction band by band
                        out_arr[band_idx][scl_mask] = apply_correction(
                            uncorrected[band_idx],
                            self.read_brdf_grid(
                                asset_name_to_l2a_band(self.item, asset),
                                resampling=resampling,
                                grid=grid,
                                brdf_config=scl_config,
                            ),
                            correction_weight=scl_config.correction_weight,
                            log10_bands_scale=scl_config.log10_bands_scale,
                        )[scl_mask]

                    # leave it be for all other cases

        return out_arr


def asset_name_to_l2a_band(item: pystac.Item, asset_name: str) -> L2ABand:
    asset = item.assets[asset_name]
    asset_path = MPath(asset.href)
    band_name = asset_path.name.split(".")[0]
    return L2ABand[band_name]
