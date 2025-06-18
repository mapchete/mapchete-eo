from __future__ import annotations

import logging
from typing import Any, List, Literal, Optional, Set

import numpy as np
import numpy.ma as ma
import pystac
import xarray as xr
from mapchete import Timer
from mapchete.io.raster import ReferencedRaster
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

    def get_mask(self) -> ReferencedRaster: ...

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

    def eo_bands_to_band_location(self, eo_bands: List[str]) -> List[BandLocation]:
        return eo_bands_to_band_locations(self.item, eo_bands)

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
            return [BandLocation(asset_name=asset) for asset in assets]
        elif eo_bands:
            return self.eo_bands_to_band_location(eo_bands)
        else:
            raise ValueError("assets or eo_bands have to be provided")


def eo_bands_to_band_locations(
    item: pystac.Item,
    eo_bands: List[str],
    role: Literal["data", "reflectance", "visual"] = "data",
) -> List[BandLocation]:
    """
    Find out location (asset and band index) of EO band.
    """
    return [find_eo_band(item, eo_band, role=role) for eo_band in eo_bands]


def find_eo_band(
    item: pystac.Item,
    eo_band_name: str,
    role: Literal["data", "reflectance", "visual"] = "data",
) -> BandLocation:
    """
    Tries to find the location of the most appropriate band using the EO band name.

    This function looks into all assets and all eo bands for the given name and role.
    """
    results = []
    for asset_name, asset in item.assets.items():
        # search in eo:bands and alternatively in bands for eo:common_name
        for band_index, band_info in enumerate(
            asset.extra_fields.get("eo:bands", asset.extra_fields.get("bands", [])), 1
        ):
            if (
                # if name matches eo band name
                (
                    eo_band_name == band_info.get("name")
                    or eo_band_name == band_info.get("eo:common_name")
                )
                # if role is given, make sure it matches with desired role
                and (asset.roles is None or role in asset.roles)
            ):
                results.append(
                    BandLocation.from_asset(
                        name=asset_name,
                        band_index=band_index,
                        asset=asset,
                    )
                )

    if len(results) == 0:
        raise KeyError(f"EO band {eo_band_name} not found in item assets")

    elif len(results) == 1:
        return results[0]

    # if results are ambiguous, further filter them
    else:
        # only use locations which seem to have the original resolution
        for matches in [_asset_name_equals_eo_name, _is_original_sampling]:
            filtered_results = [
                band_location for band_location in results if matches(band_location)
            ]
            if len(filtered_results) == 1:
                return filtered_results[0]
        else:  # pragma: no cover
            raise ValueError(
                f"EO band '{eo_band_name}' found in multiple assets: {', '.join(map(str, results))}"
            )


def _asset_name_equals_eo_name(band_location: BandLocation) -> bool:
    return band_location.asset_name == band_location.eo_band_name


def _is_original_sampling(band_location: BandLocation) -> bool:
    return band_location.roles == [] or "sampling:original" in band_location.roles


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


def blacklist_products(blacklist: Optional[MPathLike] = None) -> Set[str]:
    blacklist = blacklist or mapchete_eo_settings.blacklist
    if blacklist is None:
        raise ValueError("no blacklist is defined")
    blacklist = MPath.from_inp(blacklist)

    try:
        return set(blacklist.read_text().splitlines())
    except FileNotFoundError:
        logger.debug("%s does not exist, returning empty set", str(blacklist))
        return set()
