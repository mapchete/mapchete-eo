from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
from typing import List, Optional, Tuple

from mapchete import Timer
from mapchete.io.vector import reproject_geometry
from mapchete.types import Bounds, CRSLike
from rasterio.crs import CRS
from shapely.geometry import box, mapping, shape
from shapely.geometry.base import BaseGeometry

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
LATITUDE_BANDS = [
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "J",
    "K",
    "L",
    "M",
    "N",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
]

# column names seem to span over three UTM zones (8 per zone)
COLUMNS_PER_ZONE = 8
SQUARE_COLUMNS = [
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "J",
    "K",
    "L",
    "M",
    "N",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
    "Z",
]

# rows are weird. zone 01 starts at -80° with "M", then zone 02 with "S", then zone 03 with "M" and so on
# SQUARE_ROW_START = ["M", "S"]
SQUARE_ROW_START = ["B", "G"]
ROWS_PER_LATITUDE_BAND = 9
SQUARE_ROWS = [
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "J",
    "K",
    "L",
    "M",
    "N",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
]

# 100 x 100 km
TILE_WIDTH_M = 100_000
TILE_HEIGHT_M = 100_000
# overlap for bottom and right
TILE_OVERLAP_M = 9_800

# source point of UTM zone from where tiles start
UTM_TILE_SOURCE_LEFT = 99_960.0
UTM_TILE_SOURCE_BOTTOM = 100_040.0


@dataclass(frozen=True)
class MGRSCell:
    utm_zone: str
    latitude_band: str

    def tiles(self) -> List[S2Tile]:
        # TODO: this is incredibly slow
        def tiles_generator():
            for column_index, row_index in self._global_square_indexes():
                tile = S2Tile(
                    utm_zone=self.utm_zone,
                    latitude_band=self.latitude_band,
                    grid_square=self._global_square_index_to_grid_square(
                        column_index, row_index
                    ),
                )
                if tile.latlon_geometry.intersects(self.latlon_geometry):
                    yield tile

        return list(tiles_generator())

    def _global_square_indexes(self) -> List[Tuple[int, int]]:
        """Return global row/column indexes of squares within MGRSCell."""

        # TODO:
        # (1) reproject cell bounds to UTM
        # (2) get min/max cell index values based on tile grid source and tile width/height
        utm_bounds = Bounds(
            *reproject_geometry(
                self.latlon_geometry, src_crs="EPSG:4326", dst_crs=self.crs
            ).bounds
        )
        # min_col = math.floor((utm_bounds.left - UTM_TILE_SOURCE_LEFT) / TILE_WIDTH_M)
        # max_col = math.floor((utm_bounds.right - UTM_TILE_SOURCE_LEFT) / TILE_WIDTH_M)
        min_col = UTM_ZONES.index(self.utm_zone) * COLUMNS_PER_ZONE
        max_col = min_col + COLUMNS_PER_ZONE

        min_row = math.floor(
            (utm_bounds.bottom - UTM_TILE_SOURCE_BOTTOM) / TILE_HEIGHT_M
        )
        max_row = math.floor((utm_bounds.top - UTM_TILE_SOURCE_BOTTOM) / TILE_HEIGHT_M)
        return list(product(range(min_col, max_col + 1), range(min_row, max_row + 1)))

    def _global_square_index_to_grid_square(
        self, column_index: int, row_index: int
    ) -> str:
        # determine row offset (alternating rows at bottom start at "M" or "S")
        start_row = SQUARE_ROW_START[
            UTM_ZONES.index(self.utm_zone) % len(SQUARE_ROW_START)
        ]
        start_row_idx = SQUARE_ROWS.index(start_row)

        square_column_idx = column_index % len(SQUARE_COLUMNS)
        square_row_idx = (row_index + start_row_idx) % len(SQUARE_ROWS)

        return f"{SQUARE_COLUMNS[square_column_idx]}{SQUARE_ROWS[square_row_idx]}"

    @property
    def latlon_bounds(self) -> Bounds:
        left = LATLON_LEFT + UTM_ZONE_WIDTH * UTM_ZONES.index(self.utm_zone)
        bottom = MIN_LATITUDE + LATITUDE_BAND_HEIGHT * LATITUDE_BANDS.index(
            self.latitude_band
        )
        right = left + UTM_ZONE_WIDTH
        top = bottom + (12 if self.latitude_band == "X" else LATITUDE_BAND_HEIGHT)
        return Bounds(left, bottom, right, top)

    @property
    def crs(self) -> CRS:
        # 7 for south, 6 for north
        hemisphere = "7" if self.latitude_band < "N" else "6"
        return CRS.from_string(f"EPSG:32{hemisphere}{self.utm_zone}")

    @property
    def latlon_geometry(self) -> BaseGeometry:
        return shape(self.latlon_bounds)


@dataclass(frozen=True)
class S2Tile:
    utm_zone: str
    latitude_band: str
    grid_square: str

    @property
    def crs(self) -> CRS:
        # 7 for south, 6 for north
        hemisphere = "7" if self.latitude_band < "N" else "6"
        return CRS.from_string(f"EPSG:32{hemisphere}{self.utm_zone}")

    @property
    def bounds(self) -> Bounds:
        column_index, row_index = self._zone_square_idx()
        base_bottom = UTM_TILE_SOURCE_BOTTOM + row_index * TILE_WIDTH_M
        left = UTM_TILE_SOURCE_LEFT + column_index * TILE_WIDTH_M
        bottom = base_bottom - TILE_OVERLAP_M
        right = left + TILE_WIDTH_M + TILE_OVERLAP_M
        top = base_bottom + TILE_HEIGHT_M
        return Bounds(left, bottom, right, top)

    @property
    def __geo_interface__(self) -> dict:
        return mapping(box(*self.bounds))

    @property
    def mgrs_cell(self) -> MGRSCell:
        return MGRSCell(self.utm_zone, self.latitude_band)

    @property
    def latlon_geometry(self) -> BaseGeometry:
        return reproject_geometry(shape(self), src_crs=self.crs, dst_crs="EPSG:4326")

    @property
    def tile_id(self) -> str:
        return f"{self.utm_zone}{self.latitude_band}{self.grid_square}"

    def _global_square_idx(self) -> Tuple[int, int]:
        """
        Square index based on bottom-left corner of global AOI.

        (left: -180 and bottom: -80)
        """
        for column_index, row_index in self.mgrs_cell._global_square_indexes():
            if (
                self.mgrs_cell._global_square_index_to_grid_square(
                    column_index, row_index
                )
                == self.grid_square
            ):
                return (column_index, row_index)
        else:  # pragma: no cover
            raise ValueError("global square index could not be determined!")

    def _zone_square_idx(self) -> Tuple[int, int]:
        """Square index based on bottom-left corner of UTM zone"""
        global_column_index, global_row_index = self._global_square_idx()
        # northern zones start rows at equator
        if self.latitude_band >= "N":
            # substract latitude bands south of equator
            row_index = global_row_index - ROWS_PER_LATITUDE_BAND * len(
                [bb for bb in LATITUDE_BANDS if bb < "N"]
            )
        else:
            row_index = global_row_index
        column_index = global_column_index % COLUMNS_PER_ZONE
        return (column_index, row_index)

    @staticmethod
    def from_tile_id(tile_id: str) -> S2Tile:
        # 11SUJ
        utm_zone = tile_id[:2]
        latitude_band = tile_id[2]
        tile = tile_id[3:]
        try:
            int(utm_zone)
        except Exception:
            raise ValueError(f"invalid UTM zone given: {utm_zone}")

        return S2Tile(utm_zone=utm_zone, latitude_band=latitude_band, grid_square=tile)


def s2_tiles_from_bounds(
    left: float, bottom: float, right: float, top: float, crs: Optional[CRSLike] = None
) -> List[S2Tile]:
    bounds = Bounds(left, bottom, right, top)
    # TODO: antimeridian wrap
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

    def tiles_generator():
        for utm_zone_idx in range(min_zone_idx, max_zone_idx + 1):
            for latitude_band_idx in range(
                min_latitude_band_idx,
                min(max_latitude_band_idx + 1, len(LATITUDE_BANDS)),
            ):
                cell = MGRSCell(
                    utm_zone=UTM_ZONES[utm_zone_idx],
                    latitude_band=LATITUDE_BANDS[latitude_band_idx],
                )
                print(cell)
                for tile in cell.tiles():
                    print(tile)
                    if tile.latlon_geometry.intersects(shape(bounds)):
                        yield tile

    return list(tiles_generator())
