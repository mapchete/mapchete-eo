from __future__ import annotations

from enum import Enum
from typing import Any, Type

from pydantic import ValidationError
from pydantic.functional_validators import BeforeValidator
from typing_extensions import Annotated

from mapchete_eo.archives.base import Archive
from mapchete_eo.known_catalogs import AWSSearchCatalogS2L2A, EarthSearchV1S2L2A
from mapchete_eo.platforms.sentinel2.path_mappers import (
    EarthSearchPathMapper,
    SinergisePathMapper,
)
from mapchete_eo.platforms.sentinel2.types import ProcessingLevel
from mapchete_eo.search.config import StacSearchConfig, UTMSearchConfig


def known_archive(v: Any, **args) -> Type[Archive]:
    if isinstance(v, str):
        return KnownArchives[v].value
    elif isinstance(v, type(Archive)):
        return v
    else:
        raise ValidationError(f"cannot validate {v} to archive")


ArchiveClsFromString = Annotated[Type[Archive], BeforeValidator(known_archive)]


class AWSL2ACOGv1(Archive):
    catalog_cls = EarthSearchV1S2L2A
    collection_name = "sentinel-2-l2a"
    processing_level = ProcessingLevel.level2a
    path_mapper_cls = EarthSearchPathMapper
    default_search_cofig_cls = StacSearchConfig


class AWSL2AJP2(Archive):
    catalog_cls = AWSSearchCatalogS2L2A
    collection_name = "sentinel-s2-l2a"
    processing_level = ProcessingLevel.level2a
    path_mapper_cls = SinergisePathMapper
    default_search_cofig_cls = UTMSearchConfig


class KnownArchives(Enum):
    S2AWS_COG = AWSL2ACOGv1
    S2AWS_JP2 = AWSL2AJP2
