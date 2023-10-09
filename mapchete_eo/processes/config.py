from typing import Optional, Tuple

from pydantic import BaseModel


class RGBCompositeConfig(BaseModel):
    red: Tuple[int, int] = (0, 2300)
    green: Tuple[int, int] = (0, 2300)
    blue: Tuple[int, int] = (0, 2300)
    gamma: float = 1.15
    saturation: float = 1.3
    clahe_clip_limit: float = 3.2
    fuzzy_radius: Optional[int] = 0
    sharpen: Optional[bool] = False
    smooth_water: Optional[bool] = False
    smooth_water_ndwi_threshold: float = 0.2
