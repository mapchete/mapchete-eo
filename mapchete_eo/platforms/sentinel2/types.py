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


class CloudType(str, Enum):
    """Available cloud types in masks."""

    opaque = "opaque"
    cirrus = "cirrus"
    all = "all"


class CloudTypeBandIndex(int, Enum):
    """Band index used for rasterized cloud masks."""

    opaque = 1
    cirrus = 2


class L2ABand(int, Enum):
    """Mapping between band identifier and metadata internal band index."""

    B01 = 0
    B02 = 1
    B03 = 2
    B04 = 3
    B05 = 4
    B06 = 5
    B07 = 6
    B08 = 7
    B8A = 8
    B09 = 9
    B10 = 10
    B11 = 11
    B12 = 12


# L1CBand = Enum("L1CBand", ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10", "B11", "B12"])


class ProcessingLevel(Enum):
    """Available processing levels of Sentinel-2."""

    level1c = "L1C"
    level2a = "L2A"


class QIMask(str, Enum):
    """Available QI Masks."""

    # Finer cloud mask
    # ----------------
    # A finer cloud mask is computed on final Level-1C images. It is provided in the final
    # reference frame (ground geometry).
    clouds = "MSK_CLOUDS"

    # Detector footprint mask
    # -----------------------
    # A mask providing the ground footprint of each detector within a Tile.
    detector_footprints = "MSK_DETFOO"

    # Technical quality mask files
    # ----------------------------
    # For each spectral band, and at the same spatial resolution as that band, a raster
    # file composed of all the radiometric and technical quality masks.
    technical_quality = "MSK_QUALIT"


class QIMask_deprecated(str, Enum):
    """Masks used for Processing Baselines < 04.00"""

    # Radiometric quality masks
    # -------------------------
    # A defective pixels’ mask, containing the position of defective pixels.
    defective = "MSK_DEFECT"

    # A saturated pixels’ mask, containing the position of the saturated pixels in the
    # full resolution image.
    saturated = "MSK_SATURA"

    # A nodata pixels’ mask, containing the position of pixels with no data.
    nodata = "MSK_NODATA"


class SunAngle(str, Enum):
    zenith = "Zenith"
    azimuth = "Azimuth"


class ViewAngle(str, Enum):
    zenith = "Zenith"
    azimuth = "Azimuth"
