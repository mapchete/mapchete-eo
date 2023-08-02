"""
Models and schemas.
"""
from datetime import datetime

# from pystac import stac_link

from pydantic import BaseModel
from typing import Optional


# Models should base on STAC (items) definitions and inherit them where possible
class DataProduct(BaseModel):
    bbox: tuple
    geometry: dict
    id: str
    time: datetime
    type: str
    platform: str
    properties: dict


class StacDataProduct(DataProduct):
    collection: Optional[str] = None
    links: Optional[dict] = None
    assets: Optional[dict] = None
