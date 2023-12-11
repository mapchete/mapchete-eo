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


ProductQIMaskResolution = Enum(
    "ProductQIMaskResolution",
    {
        "20m": 20,
        "60m": 60,
    },
)


class CloudType(str, Enum):
    """Available cloud types in masks."""

    opaque = "opaque"
    cirrus = "cirrus"
    all = "all"


class ClassificationBandIndex(int, Enum):
    """Band index used for classification masks."""

    opaque = 1
    cirrus = 2
    # this is only available since PB 04.00
    snow_ice = 3


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


class ProcessingLevel(Enum):
    """Available processing levels of Sentinel-2."""

    level1c = "L1C"
    level2a = "L2A"


class ProductQI(str, Enum):
    """Product specific quality indicators."""

    classification = "classification"
    cloud_probability = "cloud_probability"
    snow_probability = "snow_probability"


class BandQI(str, Enum):
    """Band specific quality indicators."""

    detector_footprints = "detector_footprints"
    technical_quality = "technical_quality"
    # the following masks are deprecated:
    # nodata = "nodata"
    # defect = "defect"
    # saturated = "saturated"


class SunAngle(str, Enum):
    zenith = "Zenith"
    azimuth = "Azimuth"


class ViewAngle(str, Enum):
    zenith = "Zenith"
    azimuth = "Azimuth"


class SceneClassification(int, Enum):
    """Mapping of pixel values to class in SCL bands."""

    nodata = 0
    saturated_or_defected = 1
    dark_area_pixels = 2
    cloud_shadows = 3
    vegetation = 4
    not_vegetated = 5
    water = 6
    unclassified = 7
    cloud_medium_probability = 8
    cloud_high_probability = 9
    thin_cirrus = 10
    snow = 11
