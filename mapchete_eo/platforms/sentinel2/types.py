from enum import Enum


Resolution = Enum(
    "Resolution",
    {
        "original": None,
        "10m": 10,
        "20m": 20,
        "60m": 60,
        "120m": 120,
    },
)


CloudType = Enum("CloudType", ["opaque", "cirrus"])
L2ABand = Enum(
    "L2ABand",
    [
        "B01",
        "B02",
        "B03",
        "B04",
        "B05",
        "B06",
        "B07",
        "B08",
        "B8A",
        "B09",
        "B10",
        "B11",
        "B12",
    ],
)
# L1CBand = Enum("L1CBand", ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10", "B11", "B12"])


class ProcessingLevel(Enum):
    """Available processing levels of Sentinel-2."""

    level1c = "L1C"
    level2a = "L2A"


QI_MASKS = {
    # Finer cloud mask
    # ----------------
    # A finer cloud mask is computed on final Level-1C images. It is provided in the final
    # reference frame (ground geometry).
    "clouds": "MSK_CLOUDS",
    #
    # Radiometric quality masks
    # -------------------------
    # A defective pixels’ mask, containing the position of defective pixels.
    "defective": "MSK_DEFECT",
    #
    # A saturated pixels’ mask, containing the position of the saturated pixels in the
    # full resolution image.
    "saturated": "MSK_SATURA",
    #
    # A nodata pixels’ mask, containing the position of pixels with no data.
    "nodata": "MSK_NODATA",
    #
    # Detector footprint mask
    # -----------------------
    # A mask providing the ground footprint of each detector within a Tile.
    "detector_footprints": "MSK_DETFOO",
    #
    # Technical quality mask files
    # ----------------------------
    # These vector files contain a list of polygons in Level-1A reference frame indicating
    # degraded quality areas in the image.
    "technical_quality": "MSK_TECQUA",
}
