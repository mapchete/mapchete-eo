import os
from mapchete_eo.exceptions import BRDFError, MissingAsset

STAC_ALLOWED_COLLECTIONS = ["sentinel-2-l2a"]

DEFAULT_EOX_S3_CACHE = "s3://eox-mhub-cache/"

# retry settings
MP_EO_IO_RETRY_SETTINGS = {
    "tries": int(os.environ.get("MP_EO_IO_RETRY_TRIES", 3)),
    "delay": int(os.environ.get("MP_EO_RETRY_DELAY", 1)),
    "backoff": int(os.environ.get("MP_EO_IO_RETRY_BACKOFF", 1)),
}

SENTINEL2_BAND_INDEXES = {
    "L1C": {
        1: "B01",
        2: "B02",
        3: "B03",
        4: "B04",
        5: "B05",
        6: "B06",
        7: "B07",
        8: "B08",
        9: "B8A",
        10: "B09",
        11: "B10",
        12: "B11",
        13: "B12",
    },
    "L2A": {
        1: "B01_60m",
        2: "B02_10m",
        3: "B03_10m",
        4: "B04_10m",
        5: "B05_20m",
        6: "B06_20m",
        7: "B07_20m",
        8: "B08_10m",
        9: "B8A_20m",
        10: "B09_60m",
        11: "B11_20m",
        12: "B12_20m",
    },
}

VALID_PREPROCESSING_EXCEPTIONS = (MissingAsset, BRDFError)
