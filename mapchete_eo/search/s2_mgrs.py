from __future__ import annotations

import math
from dataclasses import dataclass
from functools import cached_property
from itertools import product
from typing import List, Literal, Optional, Tuple, Union

from mapchete.geometry import reproject_geometry
from mapchete.types import Bounds
from rasterio.crs import CRS
from shapely import prepare
from shapely.geometry import box, mapping, shape
from shapely.geometry.base import BaseGeometry

from mapchete_eo.geometry import (
    bounds_to_geom,
    repair_antimeridian_geometry,
    transform_to_latlon,
)

LATLON_LEFT = -180
LATLON_RIGHT = 180
LATLON_WIDTH = LATLON_RIGHT - LATLON_LEFT
LATLON_WIDTH_OFFSET = LATLON_WIDTH / 2
MIN_LATITUDE = -80.0
MAX_LATITUDE = 84
LATLON_HEIGHT = MAX_LATITUDE - MIN_LATITUDE
LATLON_HEIGHT_OFFSET = -MIN_LATITUDE

# width in degrees
UTM_ZONE_WIDTH = 6
UTM_ZONES = [f"{ii:02d}" for ii in range(1, LATLON_WIDTH // UTM_ZONE_WIDTH + 1)]

# NOTE: each latitude band is 8° high except the most northern one ("X") is 12°
LATITUDE_BAND_HEIGHT = 8
LATITUDE_BANDS = list("CDEFGHJKLMNPQRSTUVWX")

# column names seem to span over three UTM zones (8 per zone)
COLUMNS_PER_ZONE = 8
SQUARE_COLUMNS = list("ABCDEFGHJKLMNPQRSTUVWXYZ")

# rows are weird. zone 01 starts at -80° with "M", then zone 02 with "S", then zone 03 with "M" and so on
# SQUARE_ROW_START = ["M", "S"]
# SQUARE_ROW_START = ["B", "G"]  # manual offset so the naming starts on the South Pole
SQUARE_ROW_START = ["A", "F"]
SQUARE_ROWS = list("ABCDEFGHJKLMNPQRSTUV")

# 100 x 100 km
TILE_WIDTH_M = 100_000
TILE_HEIGHT_M = 100_000
# overlap for bottom and right
TILE_OVERLAP_M = 9_800

# source point of UTM zone from where tiles start
# UTM_TILE_SOURCE_LEFT = 99_960.0
UTM_TILE_SOURCE_LEFT = 100_000
UTM_TILE_SOURCE_BOTTOM = 0


class InvalidMGRSSquare(Exception):
    """Raised when an invalid square index has been given"""


@dataclass(frozen=True)
class MGRSCell:
    utm_zone: str
    latitude_band: str

    def tiles(self) -> List[S2Tile]:
        # TODO: this is incredibly slow
        def tiles_generator():
            for column_index, row_index in self._global_square_indexes:
                tile = self.tile(
                    grid_square=self._global_square_index_to_grid_square(
                        column_index, row_index
                    ),
                    column_index=column_index,
                    row_index=row_index,
                )
                if tile.latlon_geometry.intersects(self.latlon_geometry):
                    yield tile

        return list(tiles_generator())

    def tile(
        self,
        grid_square: str,
        column_index: Optional[int] = None,
        row_index: Optional[int] = None,
    ) -> S2Tile:
        if column_index is None or row_index is None:
            for column_index, row_index in self._global_square_indexes:
                if (
                    self._global_square_index_to_grid_square(column_index, row_index)
                    == grid_square
                ):
                    break
            else:  # pragma: no cover
                raise InvalidMGRSSquare(
                    f"global square index could not be determined for {self.utm_zone}{self.latitude_band}{grid_square}"
                )

        return S2Tile(
            utm_zone=self.utm_zone,
            latitude_band=self.latitude_band,
            grid_square=grid_square,
            global_column_index=column_index,
            global_row_index=row_index,
        )

    @cached_property
    def _global_square_indexes(self) -> List[Tuple[int, int]]:
        """Return global row/column indexes of squares within MGRSCell."""

        # reproject cell bounds to UTM
        utm_bounds = Bounds(
            *reproject_geometry(
                self.latlon_geometry, src_crs="EPSG:4326", dst_crs=self.crs
            ).bounds
        )
        # get min/max column index values based on tile grid source and tile width/height
        min_col = UTM_ZONES.index(self.utm_zone) * COLUMNS_PER_ZONE
        max_col = min_col + COLUMNS_PER_ZONE

        # count rows from UTM zone bottom
        min_row = math.floor(
            (utm_bounds.bottom - UTM_TILE_SOURCE_BOTTOM) / TILE_HEIGHT_M
        )
        max_row = math.floor((utm_bounds.top - UTM_TILE_SOURCE_BOTTOM) / TILE_HEIGHT_M)
        return list(product(range(min_col, max_col + 1), range(min_row, max_row + 1)))

    def _global_square_index_to_grid_square(
        self, column_index: int, row_index: int
    ) -> str:
        # determine row offset (alternating rows at bottom start at "A" or "F")
        start_row = SQUARE_ROW_START[
            UTM_ZONES.index(self.utm_zone) % len(SQUARE_ROW_START)
        ]
        start_row_idx = SQUARE_ROWS.index(start_row)

        square_column_idx = column_index % len(SQUARE_COLUMNS)
        square_row_idx = (row_index + start_row_idx) % len(SQUARE_ROWS)

        return f"{SQUARE_COLUMNS[square_column_idx]}{SQUARE_ROWS[square_row_idx]}"

    @cached_property
    def latlon_bounds(self) -> Bounds:
        left = LATLON_LEFT + UTM_ZONE_WIDTH * UTM_ZONES.index(self.utm_zone)
        bottom = MIN_LATITUDE + LATITUDE_BAND_HEIGHT * LATITUDE_BANDS.index(
            self.latitude_band
        )
        right = left + UTM_ZONE_WIDTH
        top = bottom + (12 if self.latitude_band == "X" else LATITUDE_BAND_HEIGHT)
        return Bounds(left, bottom, right, top)

    @cached_property
    def crs(self) -> CRS:
        # 7 for south, 6 for north
        hemisphere_code = "7" if self.hemisphere == "S" else "6"
        return CRS.from_string(f"EPSG:32{hemisphere_code}{self.utm_zone}")

    @cached_property
    def latlon_geometry(self) -> BaseGeometry:
        return shape(self.latlon_bounds)

    @cached_property
    def hemisphere(self) -> Union[Literal["S"], Literal["N"]]:
        return "S" if self.latitude_band < "N" else "N"


@dataclass(frozen=True)
class S2Tile:
    utm_zone: str
    latitude_band: str
    grid_square: str
    global_column_index: Optional[int] = None
    global_row_index: Optional[int] = None

    @cached_property
    def crs(self) -> CRS:
        # 7 for south, 6 for north
        hemisphere = "7" if self.latitude_band < "N" else "6"
        return CRS.from_string(f"EPSG:32{hemisphere}{self.utm_zone}")

    @cached_property
    def bounds(self) -> Bounds:
        base_bottom = UTM_TILE_SOURCE_BOTTOM + self.square_row * TILE_WIDTH_M
        left = UTM_TILE_SOURCE_LEFT + self.square_column * TILE_WIDTH_M
        bottom = base_bottom - TILE_OVERLAP_M
        right = left + TILE_WIDTH_M + TILE_OVERLAP_M
        top = base_bottom + TILE_HEIGHT_M
        return Bounds(left, bottom, right, top)

    @cached_property
    def __geo_interface__(self) -> dict:
        return mapping(box(*self.bounds))

    @cached_property
    def mgrs_cell(self) -> MGRSCell:
        return MGRSCell(self.utm_zone, self.latitude_band)

    @cached_property
    def latlon_geometry(self) -> BaseGeometry:
        # return repair_antimeridian_geometry(shape(self.latlon_bounds))
        return repair_antimeridian_geometry(transform_to_latlon(shape(self), self.crs))

    @cached_property
    def latlon_bounds(self) -> Bounds:
        return Bounds.from_inp(self.latlon_geometry)

    @cached_property
    def tile_id(self) -> str:
        return f"{self.utm_zone}{self.latitude_band}{self.grid_square}"

    @cached_property
    def square_column(self) -> int:
        if self.global_column_index is None:
            return self._global_square_idx[0] % COLUMNS_PER_ZONE
        return self.global_column_index % COLUMNS_PER_ZONE

    @cached_property
    def square_row(self) -> int:
        if self.global_row_index is None:
            return self._global_square_idx[1]
        return self.global_row_index

    @cached_property
    def _global_square_idx(self) -> Tuple[int, int]:
        """
        Square index based on bottom-left corner of global AOI.
        """
        for column_index, row_index in self.mgrs_cell._global_square_indexes:
            if (
                self.mgrs_cell._global_square_index_to_grid_square(
                    column_index, row_index
                )
                == self.grid_square
            ):
                return (column_index, row_index)
        else:  # pragma: no cover
            raise InvalidMGRSSquare(
                f"global square index could not be determined for {self.utm_zone}{self.latitude_band}{self.grid_square}"
            )

    @cached_property
    def hemisphere(self) -> Union[Literal["S"], Literal["N"]]:
        return "S" if self.latitude_band < "N" else "N"

    @staticmethod
    def from_tile_id(tile_id: str) -> S2Tile:
        tile_id = tile_id.lstrip("T")
        utm_zone = tile_id[:2]
        latitude_band = tile_id[2]
        grid_square = tile_id[3:]
        try:
            int(utm_zone)
        except Exception:
            raise ValueError(f"invalid UTM zone given: {utm_zone}")

        return MGRSCell(utm_zone, latitude_band).tile(grid_square)

    @staticmethod
    def from_grid_code(grid_code: str) -> S2Tile:
        return S2Tile.from_tile_id(grid_code.lstrip("MGRS-"))


def s2_tiles_from_bounds(
    left: float, bottom: float, right: float, top: float
) -> List[S2Tile]:
    bounds = Bounds(left, bottom, right, top)

    # determine zones in eastern-western direction
    min_zone_idx = math.floor((left + LATLON_WIDTH_OFFSET) / UTM_ZONE_WIDTH)
    max_zone_idx = math.floor((right + LATLON_WIDTH_OFFSET) / UTM_ZONE_WIDTH)

    min_latitude_band_idx = math.floor(
        (bottom + LATLON_HEIGHT_OFFSET) / LATITUDE_BAND_HEIGHT
    )
    max_latitude_band_idx = min(
        [
            math.floor((top + LATLON_HEIGHT_OFFSET) / LATITUDE_BAND_HEIGHT),
            len(LATITUDE_BANDS),
        ]
    )

    # in order to also get overlapping tiles from other UTM cells, we also
    # query the neighbors:
    min_zone_idx -= 1
    max_zone_idx += 1
    min_latitude_band_idx -= 1
    max_latitude_band_idx += 1

    aoi = bounds_to_geom(bounds)
    prepare(aoi)

    def tiles_generator():
        for utm_zone_idx in range(min_zone_idx, max_zone_idx + 1):
            for latitude_band_idx in range(
                # clamp latitude index to range of 0 and number of latitude bands
                max(min_latitude_band_idx, 0),
                min(max_latitude_band_idx + 1, len(LATITUDE_BANDS)),
            ):
                cell = MGRSCell(
                    utm_zone=UTM_ZONES[utm_zone_idx % len(UTM_ZONES)],
                    latitude_band=LATITUDE_BANDS[latitude_band_idx],
                )
                for tile in cell.tiles():
                    # bounds check seems to be faster
                    # if aoi.intersects(box(*tile.latlon_bounds)):
                    if aoi.intersects(tile.latlon_geometry):
                        yield tile

    return list(tiles_generator())
