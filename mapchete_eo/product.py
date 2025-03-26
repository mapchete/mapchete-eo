from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, List, Optional, Set

import numpy as np
import numpy.ma as ma
import pystac
import xarray as xr
from mapchete import Timer
from mapchete.path import MPath, MPathLike
from mapchete.protocols import GridProtocol
from mapchete.types import Bounds, NodataVals
from numpy.typing import DTypeLike
from rasterio.enums import Resampling
from shapely.geometry import shape

from mapchete_eo.array.convert import to_dataarray
from mapchete_eo.io import get_item_property, item_to_np_array
from mapchete_eo.protocols import EOProductProtocol
from mapchete_eo.settings import mapchete_eo_settings
from mapchete_eo.types import BandLocation

logger = logging.getLogger(__name__)


class EOProduct(EOProductProtocol):
    """Wrapper class around a pystac.Item which provides read functions."""

    default_dtype: DTypeLike = np.uint16

    def __init__(self, item: pystac.Item):
        self.item_dict = item.to_dict()
        self.__geo_interface__ = self.item.geometry
        self.bounds = Bounds.from_inp(shape(self))
        self.crs = mapchete_eo_settings.default_catalog_crs

    def __repr__(self):
        return f"<EOProduct product_id={self.item.id}>"

    def clear_cached_data(self):
        pass

    @property
    def item(self) -> pystac.Item:
        return pystac.Item.from_dict(self.item_dict)

    @classmethod
    def from_stac_item(self, item: pystac.Item, **kwargs) -> EOProduct:
        return EOProduct(item)

    def read(
        self,
        assets: Optional[List[str]] = None,
        eo_bands: Optional[List[str]] = None,
        grid: Optional[GridProtocol] = None,
        resampling: Resampling = Resampling.nearest,
        nodatavals: NodataVals = None,
        x_axis_name: str = "x",
        y_axis_name: str = "y",
        raise_empty: bool = True,
        **kwargs,
    ) -> xr.Dataset:
        """Read bands and assets into xarray."""
        # developer info: all fancy stuff for special platforms like Sentinel-2
        # should be implemented in the respective read_np_array() methods which get
        # called by this method. No need to apply masks etc. here too.
        if isinstance(nodatavals, list):
            nodataval = nodatavals[0]
        elif isinstance(nodatavals, float):
            nodataval = nodatavals
        else:
            nodataval = nodatavals

        assets = assets or []
        eo_bands = eo_bands or []
        data_var_names = assets or eo_bands
        return xr.Dataset(
            data_vars={
                data_var_name: to_dataarray(
                    asset_arr,
                    x_axis_name=x_axis_name,
                    y_axis_name=y_axis_name,
                    name=data_var_name,
                    attrs=dict(item_id=self.item.id),
                )
                for asset_arr, data_var_name in zip(
                    self.read_np_array(
                        assets=assets,
                        eo_bands=eo_bands,
                        grid=grid,
                        resampling=resampling,
                        nodatavals=nodatavals,
                        raise_empty=raise_empty,
                        **kwargs,
                    ),
                    data_var_names,
                )
            },
            coords={},
            attrs=dict(self.item.properties, id=self.item.id, _FillValue=nodataval),
        )

    def read_np_array(
        self,
        assets: Optional[List[str]] = None,
        eo_bands: Optional[List[str]] = None,
        grid: Optional[GridProtocol] = None,
        resampling: Resampling = Resampling.nearest,
        nodatavals: NodataVals = None,
        raise_empty: bool = True,
        apply_offset: bool = True,
        apply_scale: bool = False,
        **kwargs,
    ) -> ma.MaskedArray:
        assets = assets or []
        eo_bands = eo_bands or []
        bands = assets or eo_bands
        logger.debug("%s: reading assets %s over %s", self, bands, grid)
        with Timer() as t:
            out = item_to_np_array(
                self.item,
                self.assets_eo_bands_to_band_locations(assets, eo_bands),
                grid=grid,
                resampling=resampling,
                nodatavals=nodatavals,
                raise_empty=raise_empty,
                apply_offset=apply_offset,
            )
        logger.debug("%s: read in %s", self, t)
        return out

    def empty_array(
        self,
        count: int,
        grid: GridProtocol,
        fill_value: int = 0,
        dtype: Optional[DTypeLike] = None,
    ) -> ma.MaskedArray:
        shape = (count, *grid.shape)
        dtype = dtype or self.default_dtype
        return ma.MaskedArray(
            data=np.full(shape, fill_value=fill_value, dtype=dtype),
            mask=np.ones(shape, dtype=bool),
            fill_value=fill_value,
        )

    def get_property(self, property: str) -> Any:
        return get_item_property(self.item, property)

    def eo_bands_to_assets_indexes(self, eo_bands: List[str]) -> List[tuple]:
        return eo_bands_to_assets_indexes(self.item, eo_bands)

    def assets_eo_bands_to_band_locations(
        self,
        assets: Optional[List[str]] = None,
        eo_bands: Optional[List[str]] = None,
    ) -> List[BandLocation]:
        assets = assets or []
        eo_bands = eo_bands or []
        if assets and eo_bands:
            raise ValueError("assets and eo_bands cannot be provided at the same time")
        if assets:
            return [BandLocation(asset, 1) for asset in assets]
        elif eo_bands:
            return [
                BandLocation(asset, index)
                for (asset, index) in self.eo_bands_to_assets_indexes(eo_bands)
            ]
        else:
            raise ValueError("assets or eo_bands have to be provided")


def eo_bands_to_assets_indexes(item: pystac.Item, eo_bands: List[str]) -> List[tuple]:
    """
    Find out location (asset and band index) of EO band.
    """
    mapping = defaultdict(list)
    for eo_band in eo_bands:
        for asset_name, asset in item.assets.items():
            asset_eo_bands = asset.extra_fields.get("eo:bands")
            if asset_eo_bands:
                for band_idx, band_info in enumerate(asset_eo_bands, 1):
                    if eo_band == band_info.get("name"):
                        mapping[eo_band].append((asset_name, band_idx))

    for eo_band in eo_bands:
        if eo_band not in mapping:
            raise KeyError(f"EO band {eo_band} not found in item assets")
        found = mapping[eo_band]
        if len(found) > 1:
            for asset_name, band_idx in found:
                if asset_name == eo_band:
                    mapping[eo_band] = [(asset_name, band_idx)]
                    break
            else:  # pragma: no cover
                raise ValueError(
                    f"EO band {eo_band} found in multiple assets: {', '.join([f[0] for f in found])}"
                )

    return [mapping[eo_band][0] for eo_band in eo_bands]


def add_to_blacklist(path: MPathLike, blacklist: Optional[MPath] = None) -> None:
    blacklist = blacklist or mapchete_eo_settings.blacklist

    if blacklist is None:
        return

    blacklist = MPath.from_inp(blacklist)

    path = MPath.from_inp(path)

    # make sure paths stay unique
    if str(path) not in blacklist_products(blacklist):
        logger.debug("add path %s to blacklist", str(path))
        try:
            with blacklist.open("a") as dst:
                dst.write(f"{path}\n")
        except FileNotFoundError:
            with blacklist.open("w") as dst:
                dst.write(f"{path}\n")


def blacklist_products(blacklist: Optional[MPath] = None) -> Set[str]:
    blacklist = blacklist or mapchete_eo_settings.blacklist
    if blacklist is None:
        raise ValueError("no blacklist is defined")
    blacklist = MPath.from_inp(blacklist)

    try:
        with blacklist.open("r") as src:
            return set(src.read().splitlines())
    except FileNotFoundError:
        logger.debug("%s does not exist, returning empty set", str(blacklist))
        return set()
