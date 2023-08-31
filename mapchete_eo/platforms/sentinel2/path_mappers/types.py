from enum import Enum

# available product mask resolutions
ProductMaskResolution = Enum(
    "ProductMaskResolution",
    {
        "20m": 20,
        "60m": 60,
    },
)
