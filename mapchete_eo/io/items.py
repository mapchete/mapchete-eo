import logging
from typing import Any, List, Optional

import numpy.ma as ma
import pystac
from mapchete.protocols import GridProtocol
from mapchete.types import Bounds, NodataVals
from rasterio.enums import Resampling
from shapely.geometry import mapping, shape

from mapchete_eo.exceptions import EmptyProductException
from mapchete_eo.geometry import repair_antimeridian_geometry
from mapchete_eo.io.assets import asset_to_np_array
from mapchete_eo.types import BandLocation

logger = logging.getLogger(__name__)


def item_to_np_array(
    item: pystac.Item,
    band_locations: List[BandLocation],
    grid: Optional[GridProtocol] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    raise_empty: bool = False,
    apply_offset: bool = True,
) -> ma.MaskedArray:
    """
    Read window of STAC Item and merge into a 3D ma.MaskedArray.
    """
    logger.debug("reading %s assets from item %s...", len(band_locations), item.id)
    out = ma.stack(
        [
            asset_to_np_array(
                item,
                band_location.asset_name,
                indexes=band_location.band_index,
                grid=grid,
                resampling=expanded_resampling,
                nodataval=nodataval,
                apply_offset=apply_offset,
            )
            for band_location, expanded_resampling, nodataval in zip(
                band_locations,
                expand_params(resampling, len(band_locations)),
                expand_params(nodatavals, len(band_locations)),
            )
        ]
    )

    if raise_empty and out.mask.all():
        raise EmptyProductException(
            f"all required assets of {item} over grid {grid} are empty."
        )

    return out


def expand_params(param, length):
    """
    Expand parameters if they are not a list.
    """
    if isinstance(param, list):
        if len(param) != length:
            raise ValueError(f"length of {param} must be {length} but is {len(param)}")
        return param
    return [param for _ in range(length)]


def get_item_property(
    item: pystac.Item,
    property: str,
) -> Any:
    """
    Return item property.

    A valid property can be a special property like "year" from the items datetime property
    or any key in the item properties or extra_fields.

    Search order of properties is based on the pystac LayoutTemplate search order:

    https://pystac.readthedocs.io/en/stable/_modules/pystac/layout.html#LayoutTemplate
    - The object's attributes
    - Keys in the ``properties`` attribute, if it exists.
    - Keys in the ``extra_fields`` attribute, if it exists.

    Some special keys can be used in template variables:

    +--------------------+--------------------------------------------------------+
    | Template variable  | Meaning                                                |
    +====================+========================================================+
    | ``year``           | The year of an Item's datetime, or                     |
    |                    | start_datetime if datetime is null                     |
    +--------------------+--------------------------------------------------------+
    | ``month``          | The month of an Item's datetime, or                    |
    |                    | start_datetime if datetime is null                     |
    +--------------------+--------------------------------------------------------+
    | ``day``            | The day of an Item's datetime, or                      |
    |                    | start_datetime if datetime is null                     |
    +--------------------+--------------------------------------------------------+
    | ``date``           | The date (iso format) of an Item's                     |
    |                    | datetime, or start_datetime if datetime is null        |
    +--------------------+--------------------------------------------------------+
    | ``collection``     | The collection ID of an Item's collection.             |
    +--------------------+--------------------------------------------------------+
    """
    if property in ["year", "month", "day", "date", "datetime"]:
        if item.datetime is None:
            raise ValueError(
                f"STAC item has no datetime attached, thus cannot get property {property}"
            )
        elif property == "date":
            return item.datetime.date().isoformat()
        elif property == "datetime":
            return item.datetime
        else:
            return item.datetime.__getattribute__(property)
    elif property == "collection":
        return item.collection_id
    elif property in item.properties:
        return item.properties[property]
    elif property in item.extra_fields:
        return item.extra_fields[property]
    elif property == "stac_extensions":
        return item.stac_extensions
    else:
        raise KeyError(
            f"item {item.id} does not have property {property} in its datetime, properties "
            f"({', '.join(item.properties.keys())}) or extra_fields "
            f"({', '.join(item.extra_fields.keys())})"
        )


def item_fix_footprint(
    item: pystac.Item, bbox_width_threshold: float = 180.0
) -> pystac.Item:
    bounds = Bounds.from_inp(item.bbox)

    if bounds.width > bbox_width_threshold:
        logger.debug("item %s crosses Antimeridian, fixing ...", item.id)

        if item.geometry:
            geometry = repair_antimeridian_geometry(geometry=shape(item.geometry))
            item.geometry = mapping(geometry)
            item.bbox = list(geometry.bounds)

    return item
