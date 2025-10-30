from typing import List

from mapchete.path import MPathLike, MPath
from pystac import Item

from mapchete_eo.platforms.sentinel2.metadata_parser.base import S2MetadataPathMapper
from mapchete_eo.platforms.sentinel2.metadata_parser.default_path_mapper import (
    XMLMapper,
)
from mapchete_eo.platforms.sentinel2.metadata_parser.s2metadata import S2Metadata
from mapchete_eo.platforms.sentinel2.preconfigured_sources.metadata_xml_mappers import (
    EarthSearchPathMapper,
    SinergisePathMapper,
)


def guess_metadata_path_mapper(
    metadata_xml: MPathLike, **kwargs
) -> S2MetadataPathMapper:
    """Guess S2PathMapper based on URL.

    If a new path mapper is added in this module, it should also be added to this function
    in order to be detected.
    """
    metadata_xml = MPath.from_inp(metadata_xml)
    if metadata_xml.startswith(
        ("https://roda.sentinel-hub.com/sentinel-s2-l2a/", "s3://sentinel-s2-l2a/")
    ) or metadata_xml.startswith(
        ("https://roda.sentinel-hub.com/sentinel-s2-l1c/", "s3://sentinel-s2-l1c/")
    ):
        return SinergisePathMapper(metadata_xml, **kwargs)
    elif metadata_xml.startswith(
        "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/"
    ):
        return EarthSearchPathMapper(metadata_xml, **kwargs)
    else:
        return XMLMapper(metadata_xml, **kwargs)


def guess_s2metadata_from_metadata_xml(metadata_xml: MPathLike, **kwargs) -> S2Metadata:
    return S2Metadata.from_metadata_xml(
        metadata_xml=metadata_xml,
        path_mapper=guess_metadata_path_mapper(metadata_xml, **kwargs),
        **kwargs,
    )


def guess_s2metadata_from_item(
    item: Item,
    metadata_assets: List[str] = ["metadata", "granule_metadata"],
    boa_offset_fields: List[str] = [
        "sentinel:boa_offset_applied",
        "sentinel2:boa_offset_applied",
        "earthsearch:boa_offset_applied",
    ],
    processing_baseline_fields: List[str] = [
        "s2:processing_baseline",
        "sentinel:processing_baseline",
        "sentinel2:processing_baseline",
        "processing:version",
    ],
    **kwargs,
) -> S2Metadata:
    """Custom code to initialize S2Metadata from a STAC item.

    Depending on from which catalog the STAC item comes, this function should correctly
    set all custom flags such as BOA offsets or pass on the correct path to the metadata XML
    using the proper asset name.
    """
    metadata_assets = metadata_assets
    for metadata_asset in metadata_assets:
        if metadata_asset in item.assets:
            metadata_path = MPath(item.assets[metadata_asset].href)
            break
    else:  # pragma: no cover
        raise KeyError(
            f"could not find path to metadata XML file in assets: {', '.join(item.assets.keys())}"
        )

    def _determine_offset():
        for field in boa_offset_fields:
            if item.properties.get(field):
                return True

        return False

    boa_offset_applied = _determine_offset()

    if metadata_path.is_remote() or metadata_path.is_absolute():
        metadata_xml = metadata_path
    else:
        metadata_xml = MPath(item.self_href).parent / metadata_path
    for processing_baseline_field in processing_baseline_fields:
        try:
            processing_baseline = item.properties[processing_baseline_field]
            break
        except KeyError:
            pass
    else:  # pragma: no cover
        raise KeyError(
            f"could not find processing baseline version in item properties: {item.properties}"
        )
    return guess_s2metadata_from_metadata_xml(
        metadata_xml,
        processing_baseline=processing_baseline,
        boa_offset_applied=boa_offset_applied,
        **kwargs,
    )
