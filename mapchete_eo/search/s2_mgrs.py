from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

from mapchete.types import CRSLike
from rasterio.crs import CRS

LATLON_WIDTH = 360
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
SQUARE_ROW_START = ["M", "S"]
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


@dataclass
class MGRSCell:
    utm_zone: str
    latutde_band: str

    def tiles(self) -> List[S2Tile]:
        # nth global columns from left
        utm_zone_idx = UTM_ZONES.index(self.utm_zone)
        min_global_square_column_idx = utm_zone_idx * COLUMNS_PER_ZONE
        max_global_square_column_idx = min_global_square_column_idx + COLUMNS_PER_ZONE

        # nth global latitude bands from the bottom
        min_global_square_row_idx = (
            LATITUDE_BANDS.index(self.latutde_band) * ROWS_PER_LATITUDE_BAND
        )
        max_global_square_row_idx = min_global_square_row_idx + ROWS_PER_LATITUDE_BAND

        # determine row offset (alternating rows at bottom start at "M" or "S")
        start_row = SQUARE_ROW_START[utm_zone_idx % len(SQUARE_ROW_START)]
        start_row_idx = SQUARE_ROWS.index(start_row)

        tiles = []
        for global_square_column_idx in range(
            min_global_square_column_idx, max_global_square_column_idx + 1
        ):
            for global_square_row_idx in range(
                min_global_square_row_idx, max_global_square_row_idx + 1
            ):
                square_column_idx = global_square_column_idx % len(SQUARE_COLUMNS)
                square_row_idx = (global_square_row_idx + start_row_idx) % len(
                    SQUARE_ROWS
                )

                grid_square = (
                    f"{SQUARE_COLUMNS[square_column_idx]}{SQUARE_ROWS[square_row_idx]}"
                )

                tiles.append(
                    S2Tile(
                        utm_zone=self.utm_zone,
                        latitude_band=self.latutde_band,
                        grid_square=grid_square,
                    )
                )
        return tiles


@dataclass(frozen=True)
class S2Tile:
    utm_zone: str
    latitude_band: str
    grid_square: str

    @property
    def crs(self) -> CRS:
        return CRS.from_epsg()

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
    left: float, bottom: float, right: float, top: float, crs: CRSLike
) -> List[S2Tile]:
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
    tiles = []
    for utm_zone_idx in range(min_zone_idx, max_zone_idx + 1):
        for latitude_band_idx in range(
            min_latitude_band_idx, max_latitude_band_idx + 1
        ):
            cell = MGRSCell(
                utm_zone=UTM_ZONES[utm_zone_idx],
                latutde_band=LATITUDE_BANDS[latitude_band_idx],
            )
            tiles.extend(cell.tiles())
    return tiles
