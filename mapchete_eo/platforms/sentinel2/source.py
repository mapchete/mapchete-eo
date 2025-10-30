from __future__ import annotations

from typing import Optional, List, Callable, Dict, Any, Union

from pydantic import model_validator

from mapchete_eo.source import Source
from mapchete_eo.platforms.sentinel2.sources_mappers import (
    DataArchive,
    MetadataArchive,
    KNOWN_SOURCES,
)
from mapchete_eo.platforms.sentinel2.mapper_registry import MAPPER_REGISTRIES


def known_catalog_to_url(stac_catalog: str) -> str:
    if stac_catalog in KNOWN_SOURCES:
        return KNOWN_SOURCES[stac_catalog]["stac_catalog"]
    return stac_catalog


class Sentinel2Source(Source):
    """All information required to consume Sentinel-2 products."""

    # extends base model with those properties
    data_archive: Optional[DataArchive] = None
    metadata_archive: MetadataArchive = "roda"

    @property
    def item_modifier_funcs(self) -> List[Callable]:
        return [
            func
            for func in (self.get_id_mapper(), self.get_stac_metadata_mapper())
            if func is not None
        ]

    @model_validator(mode="before")
    def determine_data_source(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Handles short names of sources."""
        if isinstance(values, str):
            values = dict(stac_catalog=values)
        stac_catalog = values.get("stac_catalog", None)
        if stac_catalog in KNOWN_SOURCES:
            values.update(KNOWN_SOURCES[stac_catalog])
        else:
            # TODO: make sure catalog then is either a path or an URL
            pass
        return values

    @model_validator(mode="after")
    def verify_mappers(self) -> Sentinel2Source:
        # make sure all required mappers are registered
        self.get_id_mapper()
        self.get_stac_metadata_mapper()
        self.get_s2metadata_mapper()
        return self

    def get_id_mapper(self) -> Union[Callable, None]:
        if self.catalog_type == "static":
            return None
        for key in MAPPER_REGISTRIES["ID"]:
            if self.stac_catalog == known_catalog_to_url(key):
                return MAPPER_REGISTRIES["ID"][key]
        else:
            raise ValueError(f"no ID mapper for {self.stac_catalog} found")

    def get_stac_metadata_mapper(self) -> Union[Callable, None]:
        """Find mapper function.

        A mapper function must be provided if a custom data_archive was configured.
        """
        if self.catalog_type == "static":
            return None
        for key in MAPPER_REGISTRIES["STAC metadata"]:
            if isinstance(key, tuple):
                stac_catalog, data_archive = key
                if (
                    self.stac_catalog == known_catalog_to_url(stac_catalog)
                    and data_archive == self.data_archive
                ):
                    return MAPPER_REGISTRIES["STAC metadata"][key]
            else:
                if self.stac_catalog == known_catalog_to_url(key):
                    return MAPPER_REGISTRIES["STAC metadata"][key]
        else:
            if self.data_archive is None:
                return None
            raise ValueError(
                f"no STAC metadata mapper from {self.stac_catalog} to {self.data_archive} found"
            )

    def get_s2metadata_mapper(self) -> Union[Callable, None]:
        if self.catalog_type == "static" or self.metadata_archive is None:
            return None
        for key in MAPPER_REGISTRIES["S2Metadata"]:
            stac_catalog, metadata_archive = key
            if (
                self.stac_catalog == known_catalog_to_url(stac_catalog)
                and metadata_archive == self.metadata_archive
            ):
                return MAPPER_REGISTRIES["S2Metadata"][key]
        else:
            raise ValueError(
                f"no S2Metadata mapper from {self.stac_catalog} to {self.metadata_archive} found"
            )
