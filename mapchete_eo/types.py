from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Union

from pydantic import PositiveInt
from pystac import Asset


class GeodataType(str, Enum):
    vector = "vector"
    raster = "raster"


class MergeMethod(str, Enum):
    """
    Available methods to merge assets from multiple items.

    first: first pixel value from the list is returned
    average: average value from the list is returned
    all: any consecutive value is added and all collected are returned
    """

    first = "first"
    average = "average"
    all = "all"


DateLike = Union[str, datetime.date]
DateTimeLike = Union[DateLike, datetime.datetime]


@dataclass
class BandLocation:
    """A class representing the location of a specific band."""

    asset_name: str
    band_index: PositiveInt = 1
    nodataval: float = 0
    roles: List[str] = field(default_factory=list)
    eo_band_name: Optional[str] = None

    @staticmethod
    def from_asset(
        asset: Asset,
        name: str,
        band_index: PositiveInt,
    ) -> BandLocation:
        try:
            bands_info = asset.extra_fields.get(
                "eo:bands", asset.extra_fields.get("bands", [])
            )
            band_info = bands_info[band_index - 1]
            eo_band_name = band_info.get("eo:common_name", band_info.get("name"))
        except KeyError:
            eo_band_name = None
        return BandLocation(
            asset_name=name,
            band_index=band_index,
            nodataval=asset.extra_fields.get("nodata", 0),
            roles=asset.roles or [],
            eo_band_name=eo_band_name,
        )


@dataclass
class TimeRange:
    """A class handling time ranges."""

    start: DateTimeLike
    end: DateTimeLike
