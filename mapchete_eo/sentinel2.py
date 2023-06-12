"""
Reader driver for Sentinel-2 data.
"""
import datetime
from enum import Enum
import json
from mapchete.tile import BufferedTile
from mapchete.path import MPath
import os
from pydantic import BaseModel
from pystac import Item
from typing import Union, List, Type

from mapchete_eo import base
from mapchete_eo.archives.base import Archive
from mapchete_eo.known_catalogs import EarthSearchV0S2L2A, EarthSearchV1S2L2A
from mapchete_eo.platforms.sentinel2.metadata_parser import S2Metadata
from mapchete_eo.platforms.sentinel2.path_mappers import S2PathMapper, XMLMapper
from mapchete_eo.platforms.sentinel2.processing_baseline import ProcessingBaseline
from mapchete_eo.platforms.sentinel2.types import ProcessingLevel


# all custom path mappers and constructors are below
####################################################


class SinergisePathMapper(S2PathMapper):
    """
    Return true paths of product quality assets from the Sinergise S2 bucket.

    e.g.:
    B01 detector footprints: s3://sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/qi/MSK_DETFOO_B01.gml
    Cloud masks: s3://sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/qi/MSK_CLOUDS_B00.gml

    newer products however:
    B01 detector footprints: s3://sentinel-s2-l2a/tiles/51/K/XR/2022/6/6/0/qi/DETFOO_B01.jp2
    no vector cloudmasks available anymore
    """

    _PRE_0400_MASK_PATHS = {
        "clouds": "MSK_CLOUDS_B00.gml",
        "detector_footprints": "MSK_DETFOO_{band}.gml",
        "technical_quality": "MSK_TECQUA_{band}.gml",
        "defective": "MSK_DEFECT_{band}.gml",
        "saturated": "MSK_SATURA_{band}.gml",
        "nodata": "MSK_NODATA_{band}.gml",
    }
    _POST_0400_MASK_PATHS = {
        "clouds": "CLASSI_B00.jp2",
        "detector_footprints": "DETFOO_{band}.jp2",
        "technical_quality": "QUALIT_{band}.jp2",
    }

    def __init__(
        self,
        url: Union[MPath, str],
        bucket: str = "sentinel-s2-l2a",
        protocol: str = "s3",
        baseline_version: str = "04.00",
        **kwargs,
    ):
        url = MPath.from_inp(url)
        tileinfo_path = url.parent / "tileInfo.json"
        self._path = MPath(
            "/".join(tileinfo_path.elements[-9:-1]), **tileinfo_path._kwargs
        )
        self._utm_zone, self._latitude_band, self._grid_square = self._path.split("/")[
            1:-4
        ]
        self._baseurl = bucket
        self._protocol = protocol
        self.processing_baseline = ProcessingBaseline.from_version(baseline_version)

    def cloud_mask(self) -> str:
        if self.processing_baseline.version < "04.00":
            mask_path = self._PRE_0400_MASK_PATHS["clouds"]
        else:
            mask_path = self._POST_0400_MASK_PATHS["clouds"]
        key = f"{self._path}/qi/{mask_path}"
        return MPath.from_inp(f"{self._protocol}://{self._baseurl}/{key}")

    def _band_mask(self, qi_mask, band=None) -> str:
        try:
            if self.processing_baseline.version < "04.00":
                mask_path = self._PRE_0400_MASK_PATHS[qi_mask]
            else:
                mask_path = self._POST_0400_MASK_PATHS[qi_mask]
        except KeyError:
            raise DeprecationWarning(
                f"'{qi_mask}' quality mask not found in this product"
            )
        if band not in self._bands:
            raise KeyError(f"band must be one of {self._bands}, not {band}")
        key = f"{self._path}/qi/{mask_path.format(band=band)}"
        return MPath.from_inp(f"{self._protocol}://{self._baseurl}/{key}")

    def band_qi_mask(self, qi_mask=None, band=None) -> str:
        return self._band_mask(qi_mask=qi_mask, band=band)


class EarthSearchPathMapper(SinergisePathMapper):
    """
    The COG archive maintained by E84 and covered by EarthSearch does not hold additional data
    such as the GML files. This class maps the metadata masks to the current EarthSearch product.

    e.g.:
    B01 detector footprints: s3://sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/qi/MSK_DETFOO_B01.gml
    Cloud masks: s3://sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/qi/MSK_CLOUDS_B00.gml

    newer products however:
    B01 detector footprints: s3://sentinel-s2-l2a/tiles/51/K/XR/2022/6/6/0/qi/DETFOO_B01.jp2
    no vector cloudmasks available anymore
    """

    def __init__(
        self,
        metadata_xml: MPath,
        alternative_metadata_baseurl: str = "sentinel-s2-l2a",
        protocol: str = "s3",
        baseline_version="04.00",
        **kwargs,
    ):
        basedir = metadata_xml.parent
        tileinfo = json.loads((basedir / "tileinfo_metadata.json").read_text())
        self._path = tileinfo["path"]
        self._utm_zone, self._latitude_band, self._grid_square = basedir.elements[-6:-3]
        self._baseurl = alternative_metadata_baseurl
        self._protocol = protocol
        self.processing_baseline = ProcessingBaseline.from_version(baseline_version)


def path_mapper_guesser(
    url: str,
    **kwargs,
):
    """Guess S2PathMapper based on URL.

    If a new path mapper is added in this module, it should also be added to this function
    in order to be detected.
    """
    if url.startswith(
        ("https://roda.sentinel-hub.com/sentinel-s2-l2a/", "s3://sentinel-s2-l2a/")
    ) or url.startswith(
        ("https://roda.sentinel-hub.com/sentinel-s2-l1c/", "s3://sentinel-s2-l1c/")
    ):
        return SinergisePathMapper(url, **kwargs)
    elif url.startswith(
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/"
    ):
        return EarthSearchPathMapper(url, **kwargs)
    else:
        return XMLMapper(url, **kwargs)


def s2metadata_from_stac_item(
    item: Item,
    metadata_assets: Union[List[str], str] = ["metadata", "granule_metadata"],
    boa_offset_fields: Union[List[str], str] = [
        "sentinel:boa_offset_applied",
        "earthsearch:boa_offset_applied",
    ],
    processing_baseline_field: str = "s2:processing_baseline",
    **kwargs,
) -> "S2Metadata":
    """Custom code to initialize S2Metadate from a STAC item.

    Depending on from which catalog the STAC item comes, this function should correctly
    set all custom flags such as BOA offsets or pass on the correct path to the metadata XML
    using the proper asset name.
    """
    metadata_assets = (
        [metadata_assets] if isinstance(metadata_assets, str) else metadata_assets
    )
    for metadata_asset in metadata_assets:
        if metadata_asset in item.assets:
            metadata_path = item.assets[metadata_asset].href
            break
    else:
        raise KeyError(
            f"could not find path to metadata XML file in assets: {', '.join(item.assets.keys())}"
        )
    for field in (
        [boa_offset_fields] if isinstance(boa_offset_fields, str) else boa_offset_fields
    ):
        if item.properties.get(field):
            boa_offset_applied = True
            break
        else:
            boa_offset_applied = False
    return S2Metadata.from_metadata_xml(
        metadata_xml=metadata_path,
        processing_baseline=item.properties.get(processing_baseline_field),
        boa_offset_applied=boa_offset_applied,
        **kwargs,
    )


# this is important to add all path mappers defined here to the automated constructor
S2Metadata.path_mapper_guesser = path_mapper_guesser
# this is important to properly parse incoming pystac Items
S2Metadata.from_stac_item_constructor = s2metadata_from_stac_item


# below all supported archives are defined
##########################################


class AWSL2ACOGv0(Archive):
    catalog_cls = EarthSearchV0S2L2A
    collection_name = "sentinel-s2-l2a-cogs"
    processing_level = ProcessingLevel.level2a
    path_mapper_cls = EarthSearchPathMapper


class AWSL2ACOGv1(Archive):
    catalog_cls = EarthSearchV1S2L2A
    collection_name = "sentinel-2-l2a"
    processing_level = ProcessingLevel.level2a
    path_mapper_cls = EarthSearchPathMapper


class KnownArchives(Enum):
    S2AWS_COG = AWSL2ACOGv1
    S2AWS_COG_V0 = AWSL2ACOGv0


# here is everything we need to configure and initialize the mapchete driver
############################################################################


class FormatParams(BaseModel):
    format: str = "Sentinel-2"
    archive: Type[Archive] = KnownArchives.S2AWS_COG.value
    start_time: Union[datetime.date, datetime.datetime]
    end_time: Union[datetime.date, datetime.datetime]


METADATA: dict = {
    "driver_name": "Sentinel-2",
    "data_type": None,
    "mode": "r",
    "file_extensions": [],
}


class InputTile(base.InputTile):
    """
    Target Tile representation of input data.

    Parameters
    ----------
    tile : ``Tile``
    kwargs : keyword arguments
        driver specific parameters
    """

    def __init__(
        self,
        tile: BufferedTile,
        items: list,
        eo_bands: list,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        **kwargs,
    ) -> None:
        """Initialize."""
        self.tile = tile
        self.items = items
        self.eo_bands = eo_bands
        self.start_time = start_time
        self.end_time = end_time


class InputData(base.InputData):
    """In case this driver is used when being a readonly input to another process."""

    input_tile_cls = InputTile

    def __init__(self, input_params: dict, **kwargs) -> None:
        """Initialize."""
        super().__init__(input_params, **kwargs)
        format_params = dict_to_format_params(input_params["abstract"])
        self._bounds = input_params["delimiters"]["effective_bounds"]
        self.start_time = format_params.start_time
        self.end_time = format_params.end_time
        self.archive = format_params.archive(
            self.start_time, self.end_time, self._bounds
        )


def dict_to_format_params(format_params: dict) -> FormatParams:
    return FormatParams(**format_params)
