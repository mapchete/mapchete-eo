from __future__ import annotations

from enum import Enum
from typing import Any, Type

from mapchete.path import MPath
from pydantic import ValidationError
from pydantic.functional_validators import BeforeValidator
from pystac import Item
from typing_extensions import Annotated

from mapchete_eo.archives.base import Archive
from mapchete_eo.io.items import item_fix_footprint
from mapchete_eo.known_catalogs import (
    AWSSearchCatalogS2L2A,
    CDSESearch,
    EarthSearchV1S2L2A,
)
from mapchete_eo.platforms.sentinel2.types import ProcessingLevel
from mapchete_eo.search.s2_mgrs import S2Tile


def known_archive(v: Any, **args) -> Type[Archive]:
    if isinstance(v, str):
        return KnownArchives[v].value
    elif isinstance(v, type(Archive)):
        return v
    else:
        raise ValidationError(f"cannot validate {v} to archive")


ArchiveClsFromString = Annotated[Type[Archive], BeforeValidator(known_archive)]


def add_datastrip_id(item: Item) -> Item:
    """Make sure item metadata is following the standard."""
    # change 'sentinel2' prefix to 's2'
    properties = {k.replace("sentinel2:", "s2:"): v for k, v in item.properties.items()}

    # add datastrip id as 's2:datastrip_id'
    if not properties.get("s2:datastrip_id"):
        from mapchete_eo.platforms.sentinel2 import S2Metadata

        s2_metadata = S2Metadata.from_stac_item(item)
        properties["s2:datastrip_id"] = s2_metadata.datastrip_id

    item.properties = properties
    return item


def map_cdse_paths_to_jp2_archive(item: Item) -> Item:
    """
    CSDE has the following assets:
    AOT_10m, AOT_20m, AOT_60m, B01_20m, B01_60m, B02_10m, B02_20m, B02_60m, B03_10m, B03_20m,
    B03_60m, B04_10m, B04_20m, B04_60m, B05_20m, B05_60m, B06_20m, B06_60m, B07_20m, B07_60m,
    B08_10m, B09_60m, B11_20m, B11_60m, B12_20m, B12_60m, B8A_20m, B8A_60m, Product, SCL_20m,
    SCL_60m, TCI_10m, TCI_20m, TCI_60m, WVP_10m, WVP_20m, WVP_60m, thumbnail, safe_manifest,
    granule_metadata, inspire_metadata, product_metadata, datastrip_metadata

    sample path for AWS JP2:
    s3://sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/R10m/
    """
    band_name_mapping = {
        "AOT_10m": "aot",
        "B01_20m": "coastal",
        "B02_10m": "blue",
        "B03_10m": "green",
        "B04_10m": "red",
        "B05_20m": "rededge1",
        "B06_20m": "rededge2",
        "B07_20m": "rededge3",
        "B08_10m": "nir",
        "B09_60m": "nir09",
        "B11_20m": "swir16",
        "B12_20m": "swir22",
        "B8A_20m": "nir08",
        "SCL_20m": "scl",
        "TCI_10m": "visual",
        "WVP_10m": "wvp",
    }
    path_base_scheme = "s3://sentinel-s2-l2a/tiles/{utm_zone}/{latitude_band}/{grid_square}/{year}/{month}/{day}/{count}"
    s2tile = S2Tile.from_grid_code(item.properties["grid:code"])
    if item.datetime is None:
        raise ValueError(f"product {item.get_self_href()} does not have a timestamp")
    product_basepath = MPath(
        path_base_scheme.format(
            utm_zone=s2tile.utm_zone,
            latitude_band=s2tile.latitude_band,
            grid_square=s2tile.grid_square,
            year=item.datetime.year,
            month=item.datetime.month,
            day=item.datetime.day,
            count=0,  # TODO: get count dynamically from metadata
        )
    )
    new_assets = {}
    for asset_name, asset in item.assets.items():
        # ignore these assets
        if asset_name in [
            "Product",
            "safe_manifest",
            "product_metadata",
            "inspire_metadata",
            "datastrip_metadata",
        ]:
            continue
        # set thumbnnail
        elif asset_name == "thumbnail":
            asset.href = str(product_basepath / "R60m" / "TCI.jp2")
        # point to proper metadata
        elif asset_name == "granule_metadata":
            asset.href = str(product_basepath / "metadata.xml")
        # change band asset names and point to their new locations
        elif asset_name in band_name_mapping:
            name, resolution = asset_name.split("_")
            asset.href = product_basepath / f"R{resolution}" / f"{name}.jp2"
            asset_name = band_name_mapping[asset_name]
        else:
            continue
        new_assets[asset_name] = asset

    item.assets = new_assets

    item.properties["s2:datastrip_id"] = item.properties.get("eopf:datastrip_id")
    return item


class AWSL2ACOGv1(Archive):
    """COG archive on AWS using E84 STAC search endpoint."""

    catalog = EarthSearchV1S2L2A(
        collections=["sentinel-2-l2a"],
    )
    item_modifier_funcs = [
        item_fix_footprint,
    ]
    processing_level = ProcessingLevel.level2a


class AWSL2AJP2(Archive):
    """
    JP2000 archive on AWS using dumb S3 path guesser.
    """

    catalog = AWSSearchCatalogS2L2A(
        collections=["sentinel-s2-l2a"],
    )
    item_modifier_funcs = [
        item_fix_footprint,
        add_datastrip_id,
    ]
    processing_level = ProcessingLevel.level2a


class AWSL2AJP2CSDE(Archive):
    """
    JP2000 archive on AWS using CDSE STAC search endpoint.
    """

    catalog = CDSESearch(
        collections=["sentinel-2-l2a"],
    )
    item_modifier_funcs = [
        item_fix_footprint,
        map_cdse_paths_to_jp2_archive,
        add_datastrip_id,
    ]
    processing_level = ProcessingLevel.level2a


class CDSEL2AJP2CSDE(Archive):
    """
    JP2000 archive on CDSE (EODATA s3) using CDSE STAC search endpoint.
    """

    catalog = CDSESearch(
        collections=["sentinel-2-l2a"],
    )
    item_modifier_funcs = [
        item_fix_footprint,
        add_datastrip_id,
    ]
    processing_level = ProcessingLevel.level2a


class KnownArchives(Enum):
    S2AWS_COG = AWSL2ACOGv1
    S2AWS_JP2 = AWSL2AJP2
    S2CDSE_AWSJP2 = AWSL2AJP2CSDE
    S2CDSE_JP2 = CDSEL2AJP2CSDE
