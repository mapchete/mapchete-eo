import logging
import math
from typing import Any, List, Optional

import numpy.ma as ma
import pystac
from fiona.crs import CRS
from mapchete.io.vector import reproject_geometry
from mapchete.protocols import GridProtocol
from rasterio.enums import Resampling
from shapely.geometry import MultiPolygon, Polygon, box, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from mapchete_eo.exceptions import EmptyFootprintException, EmptyProductException
from mapchete_eo.io.assets import asset_to_np_array
from mapchete_eo.types import BandLocation, Bounds, NodataVals

logger = logging.getLogger(__name__)


def item_to_np_array(
    item: pystac.Item,
    band_locations: List[BandLocation],
    grid: Optional[GridProtocol] = None,
    resampling: Resampling = Resampling.nearest,
    nodatavals: NodataVals = None,
    raise_empty: bool = False,
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
            f"item does not have property {property} in its datetime, properties "
            f"({', '.join(item.properties.keys())}) or extra_fields "
            f"({', '.join(item.extra_fields.keys())})"
        )


def item_fix_footprint(
    item: pystac.Item, bbox_width_threshold: int = 180
) -> pystac.Item:
    bounds = Bounds.from_inp(item.bbox)

    if bounds.width > bbox_width_threshold:
        logger.debug("item %s crosses Antimeridian, fixing ...", item.id)

        if item.geometry:
            geometry = repair_antimeridian_geometry(geometry=shape(item.geometry))
            item.geometry = mapping(geometry)
            item.bbox = list(geometry.bounds)
        else:
            raise ValueError("item geometry is None")

    return item


def repair_antimeridian_geometry(geometry: BaseGeometry) -> BaseGeometry:
    if geometry.geom_type == "MultiPolygon":
        return geometry

    latlon_bbox = box(-180, -90, 180, 90)

    # (1) shift only coordinates on the western hemisphere by 360°, thus "fixing"
    # the footprint, but letting it cross the antimeridian
    shifted_geometry = longitudinal_shift(geometry, only_negative_coords=True)

    # (2) split up geometry in one outside of latlon bounds and one inside
    inside = shifted_geometry.intersection(latlon_bbox)
    outside = shifted_geometry.difference(latlon_bbox)

    # (3) shift back only the polygon outside of latlon bounds by -360, thus moving
    # it back to the western hemisphere
    outside_shifted = longitudinal_shift(outside, -360)

    # (4) create a MultiPolygon out from these two polygons
    split = unary_union([inside, outside_shifted])

    # (5) update item geometry
    return split


def longitudinal_shift(
    geometry: BaseGeometry, by: float = 360, only_negative_coords: bool = False
) -> BaseGeometry:
    if geometry.geom_type == "MultiPolygon":
        logger.debug("geometry is already a MultiPolygon and probably shifted")
        return geometry
    elif geometry.is_empty:
        return geometry

    coords = mapping(geometry)["coordinates"][0]
    out_coords = []
    for lon, lat in coords:
        if only_negative_coords:
            if lon < 0:
                lon += by
        else:
            lon += by
        out_coords.append([lon, lat])
    return shape(dict(type=geometry.geom_type, coordinates=[out_coords]))


def buffer_footprint(footprint: BaseGeometry, buffer_m: float = 0) -> BaseGeometry:
    if not buffer_m:
        return footprint

    if footprint.geom_type == "MultiPolygon":
        # we have a shifted footprint here!
        # (1) unshift one part
        subpolygons = []
        for polygon in footprint.geoms:
            lon = polygon.centroid.x
            if lon < 0:
                polygon = longitudinal_shift(polygon)
            subpolygons.append(polygon)
        # (2) merge to single polygon
        merged = unary_union(subpolygons)
        # (3) apply buffer
        buffered = buffer_footprint(merged, buffer_m=buffer_m)
        # (4) fix again
        return repair_antimeridian_geometry(buffered)

    # UTM zone CRS
    lon = footprint.centroid.x
    lat = footprint.centroid.y
    min_zone = 1
    max_zone = 60
    utm_zone = (
        f"{max([min([(math.floor((lon + 180) / 6) + 1), max_zone]), min_zone]):02}"
    )
    hemisphere_code = "7" if lat <= 0 else "6"
    utm_crs = CRS.from_string(f"EPSG:32{hemisphere_code}{utm_zone}")

    latlon_crs = CRS.from_string("EPSG:4326")
    out_geom = reproject_geometry(
        reproject_geometry(
            footprint, src_crs=latlon_crs, dst_crs=utm_crs, clip_to_crs_bounds=False
        ).buffer(buffer_m),
        src_crs=utm_crs,
        dst_crs=latlon_crs,
        clip_to_crs_bounds=False,
    )
    if out_geom.is_empty and not footprint.is_empty:
        raise EmptyFootprintException(
            f"buffer value of {buffer_m} results in an empty geometry for footprint {footprint.wkt}"
        )
    return out_geom
