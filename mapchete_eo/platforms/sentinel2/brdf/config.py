from enum import Enum
from typing import NamedTuple


class BRDFModels(str, Enum):
    none = "none"
    HLS = "HLS"
    RossThick = "RossThick"


class ModelParameters(NamedTuple):
    f_iso: float
    f_geo: float
    f_vol: float


# Source for bands outside of RGBNIR range:
# https://www.sciencedirect.com/science/article/pii/S0034425717302791
# https://www.semanticscholar.org/paper/Adjustment-of-Sentinel-2-Multi-Spectral-Instrument-Roy-Li/be90a03a19c612763f966fae5290222a4b76bba6
class L2ABandFParams(ModelParameters, Enum):
    B01 = ModelParameters(0.0774, 0.0079, 0.0372)
    B02 = ModelParameters(0.0774, 0.0079, 0.0372)
    B03 = ModelParameters(0.1306, 0.0178, 0.0580)
    B04 = ModelParameters(0.1690, 0.0227, 0.0574)
    B05 = ModelParameters(0.2085, 0.0256, 0.0845)
    B06 = ModelParameters(0.2316, 0.0273, 0.1003)
    B07 = ModelParameters(0.2599, 0.0294, 0.1197)
    B08 = ModelParameters(0.3093, 0.0330, 0.1535)
    B8A = ModelParameters(0.3093, 0.0330, 0.1535)
    B09 = ModelParameters(0.3201, 0.0471, 0.1611)
    B11 = ModelParameters(0.3430, 0.0453, 0.1154)
    B12 = ModelParameters(0.2658, 0.0387, 0.0639)
