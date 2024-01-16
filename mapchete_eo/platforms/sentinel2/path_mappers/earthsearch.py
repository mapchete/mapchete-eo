from mapchete.path import MPath

from mapchete_eo.platforms.sentinel2.path_mappers.sinergise import SinergisePathMapper
from mapchete_eo.platforms.sentinel2.processing_baseline import ProcessingBaseline


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
        baseline_version: str = "04.00",
        **kwargs,
    ):
        basedir = metadata_xml.parent
        self._path = (basedir / "tileinfo_metadata.json").read_json()["path"]
        self._utm_zone, self._latitude_band, self._grid_square = basedir.elements[-6:-3]
        self._baseurl = alternative_metadata_baseurl
        self._protocol = protocol
        self.processing_baseline = ProcessingBaseline.from_version(baseline_version)
