from enum import Enum


class BRDFModels(str, Enum):
    none = "none"
    HLS = "HLS"
    HLS_alt = "HLS_alt"
    sen2agri = "sen2agri"
    combined = "combined"
    default = "HLS"


# Source for bands outside of RGBNIR range:
# https://www.sciencedirect.com/science/article/pii/S0034425717302791
# https://www.semanticscholar.org/paper/Adjustment-of-Sentinel-2-Multi-Spectral-Instrument-Roy-Li/be90a03a19c612763f966fae5290222a4b76bba6
F_MODIS_PARAMS = {
    1: (0.0774, 0.0079, 0.0372),
    2: (0.0774, 0.0079, 0.0372),
    3: (0.1306, 0.0178, 0.0580),
    4: (0.1690, 0.0227, 0.0574),
    5: (0.2085, 0.0256, 0.0845),
    6: (0.2316, 0.0273, 0.1003),
    7: (0.2599, 0.0294, 0.1197),
    8: (0.3093, 0.0330, 0.1535),
    9: (0.3093, 0.0330, 0.1535),
    10: (0.3201, 0.0471, 0.1611),
    11: (0.3430, 0.0453, 0.1154),
    12: (0.2658, 0.0387, 0.0639),
}
