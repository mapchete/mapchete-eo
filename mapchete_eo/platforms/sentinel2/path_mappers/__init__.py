from mapchete_eo.platforms.sentinel2.path_mappers.base import S2PathMapper
from mapchete_eo.platforms.sentinel2.path_mappers.earthsearch import (
    EarthSearchPathMapper,
)
from mapchete_eo.platforms.sentinel2.path_mappers.metadata_xml import XMLMapper
from mapchete_eo.platforms.sentinel2.path_mappers.sinergise import SinergisePathMapper


def default_path_mapper_guesser(
    url: str,
    **kwargs,
) -> S2PathMapper:
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
