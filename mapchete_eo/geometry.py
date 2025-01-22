import logging
import math
from functools import partial
from typing import Callable, Iterable, Tuple

from fiona.crs import CRS
from fiona.transform import transform as fiona_transform
from mapchete.geometry import reproject_geometry
from mapchete.types import Bounds, CRSLike
from shapely.geometry import (
    GeometryCollection,
    LinearRing,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
    box,
    shape,
)
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

CoordArrays = Tuple[Iterable[float], Iterable[float]]


logger = logging.getLogger(__name__)


def transform_to_latlon(
    geometry: BaseGeometry, src_crs: CRSLike, width_threshold: float = 180.0
) -> BaseGeometry:
    """Transforms a geometry to lat/lon coordinates.

    If resulting geometry crosses the Antimeridian it will be fixed by moving coordinates
    from the Western Hemisphere to outside of the lat/lon bounds on the East, making sure
    the correct geometry shape is preserved.

    As a next step, repair_antimeridian_geometry() can be applied, which then splits up
    this geometry into a multipart geometry where all of its subgeometries are within the
    lat/lon bounds again.
    """
    latlon_crs = CRS.from_epsg(4326)

    def transform_shift_coords(coords: CoordArrays) -> CoordArrays:
        out_x_coords, out_y_coords = fiona_transform(src_crs, latlon_crs, *coords)
        if max(out_x_coords) - min(out_x_coords) > width_threshold:
            # we probably have an antimeridian crossing here!
            out_x_coords, out_y_coords = coords_longitudinal_shift(
                coords_transform(coords, src_crs, latlon_crs), only_negative_coords=True
            )
        return (out_x_coords, out_y_coords)

    return custom_transform(geometry, transform_shift_coords)


def repair_antimeridian_geometry(
    geometry: BaseGeometry, width_threshold: float = 180.0
) -> BaseGeometry:
    """
    Repair geometry and apply fix if it crosses the Antimeridian.

    A geometry crosses the Antimeridian if it is at least partly outside of the
    lat/lon bounding box or if its width exceeds a certain threshold. This can happen
    after reprojection if the geometry coordinates are transformed separately and land
    left and right of the Antimeridian, thus resulting in a polygon spanning almost the
    whole lat/lon bounding box width.
    """
    # repair geometry if it is broken
    geometry = geometry.buffer(0)
    latlon_bbox = box(-180, -90, 180, 90)

    # only attempt to fix if geometry is too wide or reaches over the lat/lon bounds
    if (
        Bounds.from_inp(geometry).width >= width_threshold
        or not geometry.difference(latlon_bbox).is_empty
    ):
        # (1) shift only coordinates on the western hemisphere by 360°, thus "fixing"
        # the footprint, but letting it cross the antimeridian
        shifted_geometry = longitudinal_shift(geometry, only_negative_coords=True)

        # (2) split up geometry in one outside of latlon bounds and one inside
        inside = shifted_geometry.intersection(latlon_bbox)
        outside = shifted_geometry.difference(latlon_bbox)

        # (3) shift back only the polygon outside of latlon bounds by -360, thus moving
        # it back to the western hemisphere
        outside_shifted = longitudinal_shift(
            outside, offset=-360, only_negative_coords=False
        )

        # (4) create a MultiPolygon out from these two polygons
        geometry = unary_union([inside, outside_shifted])

    return geometry


def buffer_antimeridian_safe(
    footprint: BaseGeometry, buffer_m: float = 0
) -> BaseGeometry:
    """Buffer geometry by meters and make it Antimeridian-safe.

    Safe means that if it crosses the Antimeridian and is a MultiPolygon,
    the buffer will only be applied to the edges facing away from the Antimeridian
    thus leaving the polygon intact if shifted back.
    """
    if footprint.is_empty:
        return footprint

    # repair geometry if it is broken
    footprint = footprint.buffer(0)

    if not buffer_m:
        return footprint

    if isinstance(footprint, MultiPolygon):
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
        if isinstance(merged, MultiPolygon):
            buffered = unary_union(
                [
                    buffer_antimeridian_safe(polygon, buffer_m=buffer_m)
                    for polygon in merged.geoms
                ]
            )
        else:
            buffered = buffer_antimeridian_safe(merged, buffer_m=buffer_m)

        # (4) fix again
        return repair_antimeridian_geometry(buffered)

    # UTM zone CRS
    utm_crs = latlon_to_utm_crs(footprint.centroid.y, footprint.centroid.x)
    latlon_crs = CRS.from_string("EPSG:4326")

    return transform_to_latlon(
        reproject_geometry(
            footprint, src_crs=latlon_crs, dst_crs=utm_crs, clip_to_crs_bounds=False
        ).buffer(buffer_m),
        src_crs=utm_crs,
    )


def longitudinal_shift(
    geometry: BaseGeometry, offset: float = 360.0, only_negative_coords: bool = False
) -> BaseGeometry:
    """Return geometry with either all or Western hemisphere coordinates shifted by some offset."""
    return custom_transform(
        geometry,
        partial(
            coords_longitudinal_shift,
            by=offset,
            only_negative_coords=only_negative_coords,
        ),
    )


def latlon_to_utm_crs(lat: float, lon: float) -> CRS:
    min_zone = 1
    max_zone = 60
    utm_zone = (
        f"{max([min([(math.floor((lon + 180) / 6) + 1), max_zone]), min_zone]):02}"
    )
    hemisphere_code = "7" if lat <= 0 else "6"
    return CRS.from_string(f"EPSG:32{hemisphere_code}{utm_zone}")


def bounds_to_geom(bounds: Bounds) -> BaseGeometry:
    # TODO: move into core package
    if bounds.left < -180:
        part1 = Bounds(-180, bounds.bottom, bounds.right, bounds.top)
        part2 = Bounds(bounds.left + 360, bounds.bottom, 180, bounds.top)
        return unary_union([shape(part1), shape(part2)])
    elif bounds.right > 180:
        part1 = Bounds(-180, bounds.bottom, bounds.right - 360, bounds.top)
        part2 = Bounds(bounds.left, bounds.bottom, 180, bounds.top)
        return unary_union([shape(part1), shape(part2)])
    else:
        return shape(bounds)


def custom_transform(geometry: BaseGeometry, func: Callable) -> BaseGeometry:
    # todo: shapely.transform.transform maybe can make this code more simple
    # https://shapely.readthedocs.io/en/stable/reference/shapely.transform.html#shapely.transform
    def _point(point: Point) -> Point:
        return Point(zip(*func(point.xy)))

    def _multipoint(multipoint: MultiPoint) -> MultiPoint:
        return MultiPoint([_point(point) for point in multipoint])

    def _linestring(linestring: LineString) -> LineString:
        return LineString(zip(*func(linestring.xy)))

    def _multilinestring(multilinestring: MultiLineString) -> MultiLineString:
        return MultiLineString(
            [_linestring(linestring) for linestring in multilinestring.geoms]
        )

    def _linearring(linearring: LinearRing) -> LinearRing:
        return LinearRing(((x, y) for x, y in zip(*func(linearring.xy))))

    def _polygon(polygon: Polygon) -> Polygon:
        return Polygon(
            _linearring(polygon.exterior),
            holes=list(map(_linearring, polygon.interiors)),
        )

    def _multipolygon(multipolygon: MultiPolygon) -> MultiPolygon:
        return MultiPolygon([_polygon(polygon) for polygon in multipolygon.geoms])

    def _geometrycollection(
        geometrycollection: GeometryCollection,
    ) -> GeometryCollection:
        return GeometryCollection(
            [_any_geometry(subgeometry) for subgeometry in geometrycollection.geoms]
        )

    def _any_geometry(geometry: BaseGeometry) -> BaseGeometry:
        transform_funcs = {
            Point: _point,
            MultiPoint: _multipoint,
            LineString: _linestring,
            MultiLineString: _multilinestring,
            Polygon: _polygon,
            MultiPolygon: _multipolygon,
            GeometryCollection: _geometrycollection,
        }
        try:
            return transform_funcs[type(geometry)](geometry)
        except KeyError:
            raise TypeError(f"unknown geometry {geometry} of type {type(geometry)}")

    if geometry.is_empty:
        return geometry

    # make valid by buffering
    return _any_geometry(geometry).buffer(0)


def coords_transform(
    coords: CoordArrays, src_crs: CRSLike, dst_crs: CRSLike
) -> CoordArrays:
    return fiona_transform(src_crs, dst_crs, *coords)


def coords_longitudinal_shift(
    coords: CoordArrays,
    by: float = 360,
    only_negative_coords: bool = False,
) -> CoordArrays:
    x_coords, y_coords = coords
    x_coords = (
        (
            x_coord + by
            if (only_negative_coords and x_coord < 0) or not only_negative_coords
            else x_coord
        )
        for x_coord in x_coords
    )
    return x_coords, y_coords
