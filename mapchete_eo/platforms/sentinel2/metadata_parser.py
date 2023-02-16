from abc import ABC, abstractmethod
from affine import Affine
from cached_property import cached_property
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
import fiona
from fiona.transform import transform_geom
from fsspec.exceptions import FSTimeoutError
import logging
from mapchete.io import fs_from_path, copy
import numpy as np
import numpy.ma as ma
import os
from pystac import Item
import rasterio
from rasterio.enums import Resampling
from rasterio.features import geometry_mask, shapes
from rasterio.fill import fillnodata
from rasterio.transform import from_bounds
from rasterio.warp import reproject
from retry import retry
from tempfile import TemporaryDirectory
from typing import Any, Dict, List, Set, Tuple, Union
import xml.etree.ElementTree as etree

from mapchete_eo.settings import MP_EO_IO_RETRY_SETTINGS


logger = logging.getLogger(__name__)


QI_MASKS = {
    # Finer cloud mask
    # ----------------
    # A finer cloud mask is computed on final Level-1C images. It is provided in the final
    # reference frame (ground geometry).
    "clouds": "MSK_CLOUDS",
    #
    # Radiometric quality masks
    # -------------------------
    # A defective pixels’ mask, containing the position of defective pixels.
    "defective": "MSK_DEFECT",
    #
    # A saturated pixels’ mask, containing the position of the saturated pixels in the
    # full resolution image.
    "saturated": "MSK_SATURA",
    #
    # A nodata pixels’ mask, containing the position of pixels with no data.
    "nodata": "MSK_NODATA",
    #
    # Detector footprint mask
    # -----------------------
    # A mask providing the ground footprint of each detector within a Tile.
    "detector_footprints": "MSK_DETFOO",
    #
    # Technical quality mask files
    # ----------------------------
    # These vector files contain a list of polygons in Level-1A reference frame indicating
    # degraded quality areas in the image.
    "technical_quality": "MSK_TECQUA",
}

CLOUD_MASK_TYPES = ["opaque", "cirrus"]
PRE_0400_MASKS = {
    "clouds",
    "defective",
    "saturated",
    "nodata",
    "detector_footprints",
    "technical_quality",
}
POST_0400_MASKS = {
    "clouds",
    "detector_footprints",
    "technical_quality",
}
PRE_0400_MASK_EXTENSION = "gml"
POST_0400_MASK_EXTENSION = "jp2"


@dataclass
class ProcessingLevel:
    level: str

    @staticmethod
    def from_string(level: str):
        if level in ["L1C", "L2A"]:
            return ProcessingLevel(level)
        else:
            return KeyError(f"unknown level: {level}")


@dataclass
class BaselineVersion:
    """Helper for Processing Baseline versions"""

    major: int
    minor: int
    level: str

    def masks(self) -> set:
        """Return set of available masks for version."""
        if self.major < 4:
            return PRE_0400_MASKS
        else:
            return POST_0400_MASKS

    def qi_band_extension(self) -> str:
        """Return file extension for QI masks."""
        if self.major < 4:
            return PRE_0400_MASK_EXTENSION
        else:
            return POST_0400_MASK_EXTENSION

    @staticmethod
    def from_string(version: str) -> "BaselineVersion":
        major, minor = map(int, version.split("."))
        if major < 2:
            raise ValueError(
                f"baseline versions below 02.00 are not supported: {version}"
            )
        # everything below 02.06 is Level 1C
        elif major == 2 and minor <= 6:
            level = "L1C"
        else:
            level = "L2A"
        return BaselineVersion(major, minor, level)

    @staticmethod
    def from_inp(inp: Union[str, "BaselineVersion"]) -> "BaselineVersion":
        if isinstance(inp, str):
            return BaselineVersion.from_string(inp)
        elif isinstance(inp, BaselineVersion):
            return inp
        else:
            raise TypeError(f"cannot generate BaselineVersion from input {inp}")

    def __eq__(self, other: Any):
        other = BaselineVersion.from_inp(other)
        return self.major == other.major and self.minor == other.minor

    def __lt__(self, other: Union[str, "BaselineVersion"]):
        other = BaselineVersion.from_inp(other)
        if self.major == other.major:
            return self.minor < other.minor
        else:
            return self.major < other.major

    def __le__(self, other: Union[str, "BaselineVersion"]):
        other = BaselineVersion.from_inp(other)
        if self.major == other.major:
            return self.minor <= other.minor
        else:
            return self.major <= other.major

    def __gt__(self, other: Union[str, "BaselineVersion"]):
        other = BaselineVersion.from_inp(other)
        if self.major == other.major:
            return self.minor > other.minor
        else:
            return self.major > other.major

    def __ge__(self, other: Union[str, "BaselineVersion"]):
        if isinstance(other, str):
            other = BaselineVersion.from_string(other)
        if self.major == other.major:
            return self.minor >= other.minor
        else:
            return self.major >= other.major


@dataclass
class ProcessingBaseline:
    version: BaselineVersion

    @staticmethod
    def from_version(version: Union[BaselineVersion, str]) -> "ProcessingBaseline":
        if isinstance(version, BaselineVersion):
            return ProcessingBaseline(version=version)
        else:
            return ProcessingBaseline(version=BaselineVersion.from_string(version))

    def available_masks(self) -> Set:
        return self.version.masks()

    def qi_band_extension(self) -> str:
        return self.version.qi_band_extension()


class S2PathMapper(ABC):
    """
    Abstract class to help mapping asset paths from metadata.xml to their
    locations of various data archives.
    """

    # All available bands for Sentinel-2 Level 1C.
    _bands = [
        "B01",
        "B02",
        "B03",
        "B04",
        "B05",
        "B06",
        "B07",
        "B08",
        "B8A",
        "B09",
        "B10",
        "B11",
        "B12",
    ]

    processing_baseline: ProcessingBaseline

    @staticmethod
    def from_xml_url(url, **kwargs) -> "S2PathMapper":
        if url.startswith(
            ("https://roda.sentinel-hub.com/sentinel-s2-l2a/", "s3://sentinel-s2-l2a/")
        ) or url.startswith(
            ("https://roda.sentinel-hub.com/sentinel-s2-l1c/", "s3://sentinel-s2-l1c/")
        ):
            # TODO maybe add more checks for invalid input URLs
            return SinergisePathMapper(
                tileinfo_path=f"{os.path.dirname(url)}/tileInfo.json", **kwargs
            )
        else:
            return XMLMapper(url, **kwargs)

    def band_name_to_id(self, band_name) -> int:
        for id, band in enumerate(self._bands):
            if band_name == band:
                return id
        else:
            raise KeyError(f"band name {band_name} not found in {self._bands}")

    @abstractmethod
    def cloud_mask(self) -> str:
        ...

    @abstractmethod
    def band_qi_mask(
        self, qi_mask: Union[str, None] = None, band=Union[str, int, None]
    ) -> str:
        ...


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
        "defective": "MSK_DEFECT_{band}.gml",
        "saturated": "MSK_SATURA_{band}.gml",
        "nodata": "MSK_NODATA_{band}.gml",
        "detector_footprints": "MSK_DETFOO_{band}.gml",
        "technical_quality": "MSK_TECQUA_{band}.gml",
    }
    _POST_0400_MASK_PATHS = {
        "clouds": "CLASSI_B00.jp2",
        "detector_footprints": "DETFOO_{band}.jp2",
        "technical_quality": "QUALIT_{band}.jp2",
    }

    def __init__(
        self,
        tileinfo_path: str,
        bucket="sentinel-s2-l2a",
        protocol="s3",
        baseline_version="04.00",
        **kwargs,
    ):
        self._path = "/".join(tileinfo_path.split("/")[-9:-1])
        self._utm_zone, self._latitude_band, self._grid_square = self._path.split("/")[
            1:-4
        ]
        self._bucket = bucket
        self._protocol = protocol
        self.processing_baseline = ProcessingBaseline.from_version(baseline_version)

    def cloud_mask(self) -> str:
        if self.processing_baseline.version < "04.00":
            mask_path = self._PRE_0400_MASK_PATHS["clouds"]
        else:
            mask_path = self._POST_0400_MASK_PATHS["clouds"]
        key = f"{self._path}/qi/{mask_path}"
        return f"{self._protocol}://{self._bucket}/{key}"

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
        return f"{self._protocol}://{self._bucket}/{key}"

    def band_qi_mask(self, qi_mask=None, band=None) -> str:
        return self._band_mask(qi_mask=qi_mask, band=band)


class XMLMapper(S2PathMapper):
    _cached_xml_root = None

    def __init__(
        self, metadata_xml: str, xml_root: Union[etree.Element, None] = None, **kwargs
    ):
        self._cached_xml_root = xml_root
        self._metadata_dir = os.path.dirname(metadata_xml)

    @cached_property
    def xml_root(self):
        if self._cached_xml_root is None:
            self._cached_xml_root = open_metadata_xml(self.metadata_xml)
        return self._cached_xml_root

    @cached_property
    def processing_baseline(self):
        # try to guess processing baseline from product id
        def _get_version(tag="TILE_ID"):
            product_id = next(self.xml_root.iter(tag)).text
            appendix = product_id.split("_")[-1]
            if appendix.startswith("N"):
                return appendix.lstrip("N")

        version = _get_version()
        try:
            return ProcessingBaseline.from_version(version)
        except Exception:
            # try use L1C product version as fallback
            try:
                l1c_version = _get_version("L1C_TILE_ID")
            except StopIteration:
                l1c_version = "02.06"
            if l1c_version is not None:
                return ProcessingBaseline.from_version(f"{l1c_version}")

    def _qi_mask_abs_path(self, qi_path) -> str:
        return os.path.join(self._metadata_dir, qi_path)

    def cloud_mask(self) -> str:
        for i in self.xml_root.iter():
            if i.tag == "MASK_FILENAME" and i.get("type") == "MSK_CLOUDS":
                return self._qi_mask_abs_path(i.text)
        else:
            raise KeyError("no MSK_CLOUDS item found in metadata")

    def _band_mask(self, qi_mask=None, band=None) -> str:
        if band not in self._bands:
            raise KeyError(f"band must be one of {self._bands}, not {band}")
        band_id = self.band_name_to_id(band)
        msk = QI_MASKS[qi_mask]
        for masks in self.xml_root.iter("Pixel_Level_QI"):
            if masks.get("geometry") == "FULL_RESOLUTION":
                for mask_path in masks:
                    if mask_path.get("type") == msk:
                        band = int(mask_path.get("bandId"))
                        if band == band_id:
                            return self._qi_mask_abs_path(mask_path.text)
                else:
                    raise KeyError(f"no {msk} for band {band_id} found in metadata")
        else:
            raise KeyError(f"no {msk} for band {band_id} found in metadata")

    def band_qi_mask(self, qi_mask=None, band=None) -> str:
        if qi_mask not in QI_MASKS:
            raise KeyError(f"invalid QI mask: {qi_mask}")
        if qi_mask not in self.processing_baseline.available_masks():
            raise DeprecationWarning(
                f"QI mask '{qi_mask}' not available for this product"
            )
        return self._band_mask(qi_mask=qi_mask, band=band)


class S2Metadata:
    _cached_xml_root = None

    def __init__(
        self,
        metadata_xml: str,
        path_mapper: S2PathMapper,
        xml_root: Union[etree.Element, None] = None,
        boa_offset: float = -1000,
        boa_offset_applied: bool = False,
        **kwargs,
    ):
        self.metadata_xml = metadata_xml
        self._cached_xml_root = xml_root
        self.path_mapper = path_mapper
        self.processing_baseline = path_mapper.processing_baseline
        self.default_boa_offset = boa_offset
        self.boa_offset_applied = boa_offset_applied
        self._metadata_dir = os.path.dirname(metadata_xml)
        self._band_masks_cache: Dict[str, dict] = {k: dict() for k in QI_MASKS.keys()}
        self._cloud_masks_cache: Union[List, None] = None
        self._viewing_incidence_angles_cache: Dict = {}

        # get geoinformation per resolution and bounds
        self.bounds, self._geoinfo = _get_bounds_geoinfo(self.xml_root)

    def __repr__(self):
        return f"<S2Metadata id={self.product_id}, processing_baseline={self.processing_baseline}>"

    @staticmethod
    def from_metadata_xml(
        metadata_xml,
        processing_baseline: Union[str, None] = None,
        path_mapper: Union[S2PathMapper, None] = None,
        guess_path_mapper: bool = True,
        **kwargs,
    ) -> "S2Metadata":
        xml_root = open_metadata_xml(metadata_xml)
        _default_path_mapper = XMLMapper(
            xml_root=xml_root, metadata_xml=metadata_xml, **kwargs
        )
        if path_mapper is None:
            if guess_path_mapper:
                path_mapper = S2PathMapper.from_xml_url(
                    url=metadata_xml,
                    xml_root=xml_root,
                    **kwargs,
                )
            else:
                path_mapper = _default_path_mapper

        # use processing baseline version from argument if available
        if processing_baseline:
            path_mapper.processing_baseline = ProcessingBaseline.from_version(
                processing_baseline
            )
        # use the information about processing baseline gained when initializing the default mapper to
        # let the path mapper generate the right paths
        else:
            path_mapper.processing_baseline = _default_path_mapper.processing_baseline

        return S2Metadata(
            metadata_xml, path_mapper=path_mapper, xml_root=xml_root, **kwargs
        )

    @staticmethod
    def from_stac_item(item: Item) -> "S2Metadata":
        for metadata_asset in ["metadata", "granule_metadata"]:
            if metadata_asset in item.assets:
                metadata_path = item.assets[metadata_asset].href
                break
        else:
            raise KeyError(
                f"could not find path to metadata XML file in assets: {', '.join(item.assets.keys())}"
            )
        return S2Metadata.from_metadata_xml(
            metadata_xml=metadata_path,
            processing_baseline=item.properties.get("sentinel:processing_baseline"),
            boa_offset_applied=item.properties.get(
                "sentinel:boa_offset_applied", False
            ),
        )

    @cached_property
    def xml_root(self):
        if self._cached_xml_root is None:
            self._cached_xml_root = open_metadata_xml(self.metadata_xml)
        return self._cached_xml_root

    @cached_property
    def product_id(self) -> str:
        return next(self.xml_root.iter("TILE_ID")).text

    @cached_property
    def datastrip_id(self) -> str:
        return next(self.xml_root.iter("DATASTRIP_ID")).text

    @cached_property
    def crs(self) -> str:
        crs_str = next(self.xml_root.iter("HORIZONTAL_CS_CODE")).text
        if not crs_str.startswith(("EPSG:326", "EPSG:327")):
            raise ValueError(f"invalid CRS given in metadata.xml: {crs_str}")
        return crs_str

    @cached_property
    def sun_angles(self) -> Dict:
        """
        Return sun angle grids.
        """
        sun_angles: dict = {"zenith": {}, "azimuth": {}}
        for angle in ["Zenith", "Azimuth"]:
            array, transform = _get_grid_data(
                group=next(self.xml_root.iter("Sun_Angles_Grid")),
                tag=angle,
                bounds=self.bounds,
            )
            mean = float(
                next(self.xml_root.iter("Mean_Sun_Angle"))
                .findall(f"{angle.upper()}_ANGLE")[0]
                .text
            )
            sun_angles[angle.lower()].update(
                array=array, transform=transform, mean=mean
            )
        return sun_angles

    @property
    def reflectance_offset(self) -> float:
        """
        Reflectance offset to be applied when reading bands.

        For baselines 04.00 and above a constant value of -1000 has to be applied
        to all reflectance bands.
        """
        if self.processing_baseline.version != "04.00" or self.boa_offset_applied:
            return 0
        else:
            return self.default_boa_offset

    def shape(self, resolution) -> Tuple:
        """
        Return grid shape for resolution.

        Parameters
        ----------
        resolution : str
            Either '10m', '20m' or '60m'.

        Returns
        -------
        tuple of (height, width)
        """
        return self._geoinfo[resolution]["shape"]

    def pixel_x_size(self, resolution) -> float:
        """
        Return horizontal pixel size for resolution.

        Parameters
        ----------
        resolution : str
            Either '10m', '20m' or '60m'.

        Returns
        -------
        float
        """
        return self._geoinfo[resolution]["x_size"]

    def pixel_y_size(self, resolution) -> float:
        """
        Return vertical pixel size for resolution.

        Parameters
        ----------
        resolution : str
            Either '10m', '20m' or '60m'.

        Returns
        -------
        float
        """
        return self._geoinfo[resolution]["y_size"]

    def transform(self, resolution) -> Affine:
        """
        Return Affine object for resolution.

        Parameters
        ----------
        resolution : str
            Either '10m', '20m' or '60m'.

        Returns
        -------
        Affine()
        """
        return self._geoinfo[resolution]["transform"]

    def cloud_mask(self, mask_type=None) -> List[Dict]:
        """
        Return cloud mask.

        Returns
        -------
        List of GeoJSON mappings.
        """
        if mask_type is None:
            mask_type = CLOUD_MASK_TYPES
        elif isinstance(mask_type, str):
            mask_type = [mask_type]
        elif isinstance(mask_type, (list, tuple)):
            pass
        else:
            raise TypeError(
                f"mask_type must be either 'None' or one of  {CLOUD_MASK_TYPES}"
            )
        for m in mask_type:
            if m not in CLOUD_MASK_TYPES:
                raise ValueError(
                    f"mask type must be one of {CLOUD_MASK_TYPES}, not {m}"
                )
        if self._cloud_masks_cache is None:
            mask_path = self.path_mapper.cloud_mask()

            band_idx_cloud_type = {1: "OPAQUE", 2: "CIRRUS"}

            if mask_path.endswith(".jp2"):
                features = []
                # read opaque mask
                for f in self._vectorize_raster_mask(mask_path, indexes=[1, 2]):
                    band_idx = f["properties"].pop("_band_idx")
                    f["properties"]["maskType"] = band_idx_cloud_type[band_idx]
                    features.append(f)
            else:
                features = self._read_vector_mask(mask_path)
            self._cloud_masks_cache = features
        return [
            f
            for f in self._cloud_masks_cache
            if f["properties"]["maskType"].lower() in mask_type
        ]

    def detector_footprints(self, band_idx) -> List[Dict]:
        """
        Return detector footprints.

        Paramerters
        -----------
        band_idx : int
            Band index.

        Returns
        -------
        List of GeoJSON mappings.
        """
        footprints = self._get_band_mask(band_idx, "detector_footprints")
        if len(footprints) == 0:
            raise MissingAsset(
                f"No detector footprints found for band {band_idx} in {self}"
            )
        return footprints

    def defective_mask(self, band_idx) -> List[Dict]:
        """
        Return defective mask.

        Paramerters
        -----------
        band_idx : int
            Band index.

        Returns
        -------
        List of GeoJSON mappings.
        """
        return self._get_band_mask(band_idx, "defective")

    def saturated_mask(self, band_idx) -> List[Dict]:
        """
        Return saturated mask.

        Paramerters
        -----------
        band_idx : int
            Band index.

        Returns
        -------
        List of GeoJSON mappings.
        """
        return self._get_band_mask(band_idx, "saturated")

    def nodata_mask(self, band_idx) -> List[Dict]:
        """
        Return nodata mask.

        Paramerters
        -----------
        band_idx : int
            Band index.

        Returns
        -------
        List of GeoJSON mappings.
        """
        return self._get_band_mask(band_idx, "nodata")

    def technical_quality_mask(self, band_idx) -> List[Dict]:
        """
        Return technical quality mask.

        Paramerters
        -----------
        band_idx : int
            Band index.

        Returns
        -------
        List of GeoJSON mappings.
        """
        return self._get_band_mask(band_idx, "technical_quality")

    def viewing_incidence_angles(self, band_idx) -> Dict:
        """
        Return viewing incidence angles.

        Paramerters
        -----------
        band_idx : int
            Band index.

        Returns
        -------
        Dictionary of 'zenith' and 'azimuth' angles.

        Example
        -------
            {
                "zenith": {
                    "mean": float --> mean angle
                    "detector": {
                        1: { --> detector ID (same as in viewing angles)
                            "array": np.ma.MaskedArray --> zenith angles grid
                            "transform": Affine --> geotransform object
                        }
                        ...
                    }
                },
                "azimuth": {
                    "mean": float --> mean angle
                    "detector": {
                        1: { --> detector ID (same as in viewing angles)
                            "array": np.ma.MaskedArray --> azimuth angles grid
                            "transform": Affine --> geotransform object
                        }
                        ...
                    }
                }
            }
        """
        if self._viewing_incidence_angles_cache.get(band_idx) is None:
            angles: Dict[str, Any] = {
                "zenith": {"detector": dict(), "mean": None},
                "azimuth": {"detector": dict(), "mean": None},
            }
            for grids in self.xml_root.iter("Viewing_Incidence_Angles_Grids"):
                band = int(grids.get("bandId")) + 1
                if band == band_idx:
                    detector = int(grids.get("detectorId"))
                    for angle in ["Zenith", "Azimuth"]:
                        array, transform = _get_grid_data(
                            group=grids, tag=angle, bounds=self.bounds
                        )
                        angles[angle.lower()]["detector"][detector] = dict(
                            array=array, transform=transform
                        )
            for band_angles in self.xml_root.iter("Mean_Viewing_Incidence_Angle_List"):
                for band_angle in band_angles:
                    band = int(band_angle.get("bandId")) + 1
                    if band == band_idx:
                        for angle in ["Zenith", "Azimuth"]:
                            angles[angle.lower()].update(
                                mean=float(
                                    band_angle.findall(f"{angle.upper()}_ANGLE")[0].text
                                )
                            )

            self._viewing_incidence_angles_cache[band_idx] = angles
        return self._viewing_incidence_angles_cache[band_idx]

    def viewing_incidence_angle(self, band_idx, detector_id, angle="zenith") -> Dict:
        return self.viewing_incidence_angles(band_idx)[angle]["detector"][detector_id]

    def mean_viewing_incidence_angles(
        self,
        band_ids=None,
        angle="zenith",
        resolution="60m",
        resampling="bilinear",
        smoothing_iterations=10,
    ) -> np.ndarray:
        band_ids = band_ids or list(range(1, 14))
        if isinstance(band_ids, int):
            band_ids = [band_ids]
        if angle not in ["zenith", "azimuth"]:
            raise ValueError("angle must be either 'zenith' or 'azimuth'")

        def _band_angles(band_id):
            detector_angles = self.viewing_incidence_angles(band_id)[angle]["detector"]
            band_angles = ma.masked_equal(
                np.zeros(self.shape(resolution), dtype=np.float32), 0
            )
            # for detector in detectors.values():
            for detector in self.detector_footprints(band_id):
                detector_id = int(detector["id"])
                # handle rare cases where detector geometries are available but no respective
                # angle arrays:
                if detector_id not in detector_angles:  # pragma: no cover
                    logger.debug(
                        f"no {angle} angles grid found for detector {detector_id}"
                    )
                    continue

                # interpolate missing nodata edges and return BRDF difference model
                detector_array = ma.masked_invalid(
                    fillnodata(
                        detector_angles[detector_id]["array"],
                        smoothing_iterations=smoothing_iterations,
                    )
                )

                # resample detector angles to output resolution
                detector_angle = _resample_array(
                    in_array=detector_array,
                    in_transform=detector_angles[detector_id]["transform"],
                    in_crs=self.crs,
                    nodata=0,
                    dst_transform=self.transform(resolution),
                    dst_crs=self.crs,
                    dst_shape=self.shape(resolution),
                    resampling=resampling,
                )
                detector_mask = geometry_mask(
                    [transform_geom(self.crs, self.crs, detector["geometry"])],
                    self.shape(resolution),
                    self.transform(resolution),
                    all_touched=False,
                    invert=False,
                )
                # merge detector stripes
                band_angles[~detector_mask] = detector_angle[~detector_mask]
                band_angles.mask[~detector_mask] = detector_angle.mask[~detector_mask]

            return band_angles

        return ma.mean(
            ma.stack([_band_angles(band_id) for band_id in band_ids]), axis=0
        )

    def _get_band_mask(self, band_idx, qi_mask):
        if self._cache["band_masks"].get(qi_mask, {}).get(band_idx) is None:
            mask_path = self.path_mapper.band_qi_mask(
                qi_mask=qi_mask, band=self._band_idx_to_name(band_idx)
            )
            if mask_path.endswith(".jp2"):
                features = self._vectorize_raster_mask(mask_path)
                # append detector ID for detector footprints
                if qi_mask == "detector_footprints":
                    for f in features:
                        f["properties"]["detector_id"] = int(
                            f["properties"].pop("value")
                        )
            else:
                features = self._read_vector_mask(mask_path)
                # append detector ID for detector footprints
                if qi_mask == "detector_footprints":
                    for f in features:
                        detector_id = int(f["properties"]["gml_id"].split("-")[-2])
                        f["id"] = detector_id
                        f["properties"]["detector_id"] = detector_id

            self._cache["band_masks"][qi_mask][band_idx] = features

        return self._cache["band_masks"][qi_mask][band_idx]

    @staticmethod
    def _read_vector_mask(mask_path):
        logger.debug(f"open {mask_path} with Fiona")
        with _cached_path(mask_path) as cached:
            try:
                with fiona.open(cached) as src:
                    return list([dict(f) for f in src])
            except ValueError as e:
                # this happens if GML file is empty
                if str(
                    e
                ) == "Null layer: ''" or "'hLayer' is NULL in 'OGR_L_GetName'" in str(
                    e
                ):
                    return []
                else:  # pragma: no cover
                    raise

    @staticmethod
    def _vectorize_raster_mask(mask_path, indexes=[1]):
        logger.debug(f"open {mask_path} with rasterio")

        def _gen():
            with _cached_path(mask_path) as cached:
                with rasterio.open(cached) as src:
                    for index in indexes:
                        arr = src.read(index)
                        mask = np.where(arr == 0, False, True)
                        for id_, (polygon, value) in enumerate(
                            shapes(arr, mask=mask, transform=src.transform), 1
                        ):
                            out = {
                                "id": id_,
                                "geometry": polygon,
                                "properties": {"value": value},
                            }
                            if len(indexes) > 1:
                                out["properties"]["_band_idx"] = index
                            yield out

        return list(_gen())

    def _band_idx_to_name(self, band_idx):
        # band indexes start at 1
        for idx, band_name in enumerate(
            [
                "B01",
                "B02",
                "B03",
                "B04",
                "B05",
                "B06",
                "B07",
                "B08",
                "B8A",
                "B09",
                "B10",
                "B11",
                "B12",
            ],
            1,
        ):
            if band_idx == idx:
                return band_name
        else:
            raise KeyError(f"cannot assign band index {band_idx} to band name")


@retry(
    logger=logger,
    exceptions=(TimeoutError, FSTimeoutError),
    **MP_EO_IO_RETRY_SETTINGS,
)
def open_metadata_xml(metadata_xml):
    logger.debug(f"open {metadata_xml}")
    with fs_from_path(metadata_xml).open(metadata_xml, "r") as metadata:
        return etree.fromstring(metadata.read())


@contextmanager
def _cached_path(path, timeout=5, requester_payer="requester", region="eu-central-1"):
    """If path is remote, download to temporary directory and return path."""
    if path.startswith(("s3://", "http://", "https://")):
        with TemporaryDirectory() as tempdir:
            tempfile = os.path.join(tempdir, os.path.basename(path))
            logger.debug(f"{path} is remote, download to {tempfile}")
            copy(
                path,
                tempfile,
            )
            yield tempfile
    else:
        yield path


def _get_bounds_geoinfo(root):
    geoinfo = {
        "10m": {},
        "20m": {},
        "60m": {},
        "120m": {},
    }
    for size in root.iter("Size"):
        resolution = f"{size.get('resolution')}m"
        for item in size:
            if item.tag == "NROWS":
                height = int(item.text)
            elif item.tag == "NCOLS":
                width = int(item.text)
        geoinfo[resolution] = dict(shape=(height, width))
    for geoposition in root.iter("Geoposition"):
        resolution = f"{geoposition.get('resolution')}m"
        for item in geoposition:
            if item.tag == "ULX":
                left = float(item.text)
            elif item.tag == "ULY":
                top = float(item.text)
            elif item.tag == "XDIM":
                x_size = float(item.text)
            elif item.tag == "YDIM":
                y_size = float(item.text)
        right = left + width * x_size
        bottom = top + height * y_size
        bounds = (left, bottom, right, top)
        geoinfo[resolution].update(
            x_size=x_size,
            y_size=y_size,
            transform=from_bounds(left, bottom, right, top, width, height),
        )
    for additional_resolution in [120]:
        resolution = f"{additional_resolution}m"
        width_10m, height_10m = geoinfo["10m"]["shape"]
        relation = additional_resolution // 10
        width = width_10m // relation
        height = height_10m // relation
        x_size = geoinfo["10m"]["x_size"] * relation
        y_size = geoinfo["10m"]["y_size"] * relation
        geoinfo[resolution].update(
            shape=(height, width),
            x_size=x_size,
            y_size=y_size,
            transform=from_bounds(left, bottom, right, top, width, height),
        )
    return bounds, geoinfo


def _get_grid_data(group, tag, bounds):
    def _get_grid(values_list):
        return ma.masked_invalid(
            np.array(
                [
                    [
                        np.nan if cell == "NaN" else float(cell)
                        for cell in row.text.split()
                    ]
                    for row in values_list
                ],
                dtype=np.float32,
            )
        )

    def _get_affine(bounds=None, row_step=None, col_step=None, shape=None):
        left, bottom, right, top = bounds
        height, width = shape

        angles_left = left - col_step / 2
        angles_right = angles_left + col_step * width
        angles_top = top + row_step / 2
        angles_bottom = angles_top - row_step * height

        return from_bounds(
            angles_left, angles_bottom, angles_right, angles_top, width, height
        )

    items = group.findall(tag)[0]
    col_step = int(items.findall("COL_STEP")[0].text)
    row_step = int(items.findall("ROW_STEP")[0].text)
    grid = _get_grid(items.findall("Values_List")[0])
    affine = _get_affine(
        bounds=bounds, row_step=row_step, col_step=col_step, shape=grid.shape
    )
    return grid, affine


def _resample_array(
    in_array=None,
    in_transform=None,
    in_crs=None,
    nodata=0,
    dst_transform=None,
    dst_crs=None,
    dst_shape=None,
    resampling="bilinear",
):
    dst_data = np.empty(dst_shape, in_array.dtype)
    reproject(
        in_array,
        dst_data,
        src_transform=in_transform,
        src_crs=in_crs,
        src_nodata=nodata,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        dst_nodata=nodata,
        resampling=Resampling[resampling],
    )
    return ma.masked_array(
        data=np.nan_to_num(dst_data, nan=nodata),
        mask=ma.masked_invalid(dst_data).mask,
        fill_value=nodata,
    )


class MissingAsset(Exception):
    """Raised when a product asset should contain data but is empty."""
