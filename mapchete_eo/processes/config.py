from __future__ import annotations

from typing import Dict, Optional, Tuple, Union

from pydantic import BaseModel


class SmoothConfig(BaseModel):
    radius: Optional[int] = 1
    smooth_more: Optional[bool] = False

    @staticmethod
    def parse(inp: Union[SmoothConfig, dict]) -> SmoothConfig:
        if isinstance(inp, SmoothConfig):
            return inp
        elif isinstance(inp, dict):
            return SmoothConfig(**inp)
        else:
            raise TypeError(f"cannot parse SmoothConfig from {inp}")


class RGBCompositeConfig(BaseModel):
    red: Tuple[int, int] = (0, 2300)
    green: Tuple[int, int] = (0, 2300)
    blue: Tuple[int, int] = (0, 2300)
    gamma: float = 1.15
    saturation: float = 1.3
    clahe_flag: bool = True
    clahe_clip_limit: float = 3.2
    clahe_tile_grid_size: Tuple[int, int] = (32, 32)
    sigmoidal_flag: bool = False
    sigmoidal_contrast: int = 0
    sigmoidal_bias: float = 0.0
    fuzzy_radius: Optional[int] = 0
    sharpen: Optional[bool] = False
    smooth: Optional[bool] = False
    smooth_config: SmoothConfig = SmoothConfig()
    smooth_water: Optional[bool] = False
    smooth_water_config: SmoothConfig = SmoothConfig(radius=6, smooth_more=True)
    smooth_water_ndwi_threshold: float = 0.2
    calculations_dtype: str = "float16"

    @staticmethod
    def parse(inp: Union[RGBCompositeConfig, Dict]) -> RGBCompositeConfig:
        if isinstance(inp, RGBCompositeConfig):
            return inp
        elif isinstance(inp, dict):
            smooth_config = SmoothConfig.parse(inp.pop("smooth_config", {}))
            return RGBCompositeConfig(smooth_config=smooth_config, **inp)
        else:
            raise TypeError(f"cannot parse RGBCompositeConfig from {inp}")
