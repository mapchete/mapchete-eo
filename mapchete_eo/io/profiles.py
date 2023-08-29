from rasterio.profiles import Profile


class COGDeflateProfile(Profile):
    """Standard COG profile."""

    defaults = {
        "driver": "COG",
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "compress": "DEFLATE",
    }


class JP2LossyProfile(Profile):
    """Very lossy JP2 profile used for low size test data."""

    defaults = {
        "driver": "JP2OpenJPEG",
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "quality": 50,
    }


class JP2LosslessProfile(Profile):
    """Lossless JP2 profile used for lower size data."""

    defaults = {
        "driver": "JP2OpenJPEG",
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "quality": 100,
        "reversible": True,
    }


rio_profiles = {
    "cog_deflate": COGDeflateProfile(),
    "jp2_lossy": JP2LossyProfile(),
    "jp2_lossless": JP2LosslessProfile(),
}
