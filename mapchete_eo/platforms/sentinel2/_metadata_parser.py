"""
A metadata parser helps to read additional Sentinel-2 metadata such as
sun angles, quality masks, etc.
"""

import logging
import xml.etree.ElementTree as etree
from contextlib import contextmanager
from functools import cached_property
from tempfile import TemporaryDirectory
from typing import Any, Callable, Dict, List, Tuple, Union

import numpy as np
import numpy.ma as ma
from affine import Affine
from fiona.transform import transform_geom
from mapchete import Timer
from mapchete.io import copy, fiona_open, rasterio_open
from mapchete.io.raster import ReferencedRaster
from mapchete.path import MPath
from mapchete.types import Bounds
from pystac import Item
from rasterio.crs import CRS
from rasterio.features import geometry_mask, shapes
from rasterio.fill import fillnodata
from rasterio.transform import from_bounds
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

from mapchete_eo.array.resampling import resample_array
from mapchete_eo.exceptions import MissingAsset
from mapchete_eo.io import open_xml
from mapchete_eo.platforms.sentinel2.path_mappers import S2PathMapper, XMLMapper
from mapchete_eo.platforms.sentinel2.processing_baseline import ProcessingBaseline
from mapchete_eo.platforms.sentinel2.types import (
    BandQIMask,
    ClassificationBandIndex,
    CloudType,
    L2ABand,
    ProductQIMask,
    Resolution,
    SunAngle,
    ViewAngle,
)

logger = logging.getLogger(__name__)


def _default_path_mapper_guesser(*args, **kwargs):
    return XMLMapper(*args, **kwargs)


def _default_from_stac_item_constructor(
    item: Item,
    **kwargs,
) -> "S2Metadata":
    return S2Metadata.from_metadata_xml(
        metadata_xml=item.assets["metadata"].href,
        **kwargs,
    )


class S2Metadata:
    _cached_xml_root = None
    path_mapper_guesser: Callable = _default_path_mapper_guesser
    from_stac_item_constructor: Callable = _default_from_stac_item_constructor
    crs: CRS
    bounds: Bounds

    def __init__(
        self,
        metadata_xml: MPath,
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
        self._metadata_dir = metadata_xml.parent
        self._band_masks_cache: Dict[str, dict] = {mask: dict() for mask in BandQIMask}
        self._cloud_masks_cache: Union[List, None] = None
        self._viewing_incidence_angles_cache: Dict = {}

        # get geoinformation per resolution and bounds
        self.bounds, self._geoinfo = _get_bounds_geoinfo(self.xml_root)
        self.footprint = shape(self.bounds)
        self.crs = self._crs

    def __repr__(self):
        return f"<S2Metadata id={self.product_id}, processing_baseline={self.processing_baseline}>"

    @property
    def __geo_interface__(self) -> dict:
        return mapping(self.footprint)

    @property
    def footprint_latlon(self) -> BaseGeometry:
        return shape(
            transform_geom(
                src_crs=self.crs,
                dst_crs="EPSG:4326",
                geom=self.__geo_interface__,
                antimeridian_cutting=True,
            )
        )

    @classmethod
    def from_metadata_xml(
        cls,
        metadata_xml: Union[str, MPath],
        processing_baseline: Union[str, None] = None,
        path_mapper: Union[S2PathMapper, None] = None,
        **kwargs,
    ) -> "S2Metadata":
        metadata_xml = MPath.from_inp(metadata_xml, **kwargs)
        xml_root = open_xml(metadata_xml)
        if path_mapper is None:
            # guess correct path mapper
            path_mapper = cls.path_mapper_guesser(
                metadata_xml,
                xml_root=xml_root,
                **kwargs,
            )

        # use processing baseline version from argument if available
        if processing_baseline:
            path_mapper.processing_baseline = ProcessingBaseline.from_version(
                processing_baseline
            )
        # use the information about processing baseline gained when initializing the default mapper to
        # let the path mapper generate the right paths
        else:
            _default_path_mapper = XMLMapper(
                xml_root=xml_root, metadata_xml=metadata_xml, **kwargs
            )
            path_mapper.processing_baseline = _default_path_mapper.processing_baseline

        return S2Metadata(
            metadata_xml, path_mapper=path_mapper, xml_root=xml_root, **kwargs
        )

    @classmethod
    def from_stac_item(cls, item: Item, **kwargs) -> "S2Metadata":
        return cls.from_stac_item_constructor(item, **kwargs)

    @cached_property
    def xml_root(self):
        if self._cached_xml_root is None:
            self._cached_xml_root = open_xml(self.metadata_xml)
        return self._cached_xml_root

    @cached_property
    def product_id(self) -> str:
        return next(self.xml_root.iter("TILE_ID")).text

    @cached_property
    def datastrip_id(self) -> str:
        return next(self.xml_root.iter("DATASTRIP_ID")).text

    @cached_property
    def _crs(self) -> CRS:
        crs_str = next(self.xml_root.iter("HORIZONTAL_CS_CODE")).text
        return CRS.from_string(crs_str)

    @cached_property
    def bands_dict(self) -> dict:
        return {}

    @cached_property
    def masks_dict(self) -> dict:
        return {}

    @cached_property
    def sun_angles(self) -> Dict:
        """
        Return sun angle grids.
        """
        sun_angles: dict = {angle: dict() for angle in SunAngle}
        for angle in SunAngle:
            raster = _get_grid_data(
                group=next(self.xml_root.iter("Sun_Angles_Grid")),
                tag=angle,
                bounds=self.bounds,
                crs=self.crs,
            )
            mean = float(
                next(self.xml_root.iter("Mean_Sun_Angle"))
                .findall(f"{angle.value.upper()}_ANGLE")[0]
                .text
            )
            sun_angles[angle].update(raster=raster, mean=mean)
        return sun_angles

    @property
    def reflectance_offset(self) -> float:
        """
        Reflectance offset of -1000 to be applied when reading bands.
        """
        if self.boa_offset_applied:
            return self.default_boa_offset
        else:
            return 0

    @property
    def assets(self) -> dict:
        """
        Mapping of all available metadata assets such as QI bands
        """
        out = dict()
        for product_qi_mask in ProductQIMask:
            out[product_qi_mask.name] = self.path_mapper.product_qi_mask(
                product_qi_mask
            )

        for band_qi_mask in BandQIMask:
            for band in L2ABand:
                out[f"{band.name}-{band_qi_mask.name}"] = self.path_mapper.band_qi_mask(
                    qi_mask=band_qi_mask, band=band
                )

        return out

    def shape(self, resolution: Resolution) -> Tuple:
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

    def pixel_x_size(self, resolution: Resolution) -> float:
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

    def pixel_y_size(self, resolution: Resolution) -> float:
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

    def transform(self, resolution: Resolution) -> Affine:
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

    def cloud_mask(self, mask_type: CloudType = CloudType.all) -> List[Dict]:
        """
        Return cloud mask.

        Returns
        -------
        List of GeoJSON mappings.
        """
        if mask_type == CloudType.all:
            mask_types_strings = [i.value for i in CloudType if i != CloudType.all]
        else:
            mask_types_strings = [mask_type.value]
        if self._cloud_masks_cache is None:
            mask_path = self.path_mapper.classification_mask()

            if mask_path.endswith(".jp2"):
                features = []
                for f in self._vectorize_raster_mask(
                    mask_path,
                    indexes=[
                        i.value
                        for i in ClassificationBandIndex
                        if i.value in mask_types_strings
                    ],
                ):
                    band_idx = f["properties"].pop("_band_idx")
                    for cloud_type_index in ClassificationBandIndex:
                        if band_idx == cloud_type_index.value:
                            f["properties"]["maskType"] = cloud_type_index.name
                            break
                    else:
                        raise KeyError(
                            f"unknown band index {band_idx} for cloud bands: {list(CloudType)}"
                        )
                    features.append(f)
            else:
                features = self._read_vector_mask(mask_path)
            self._cloud_masks_cache = features
        return [
            f
            for f in self._cloud_masks_cache
            if f["properties"]["maskType"].lower() in mask_types_strings
        ]

    def detector_footprints(self, band: L2ABand) -> List[Dict]:
        """
        Return detector footprints.

        Paramerters
        -----------
        band_idx : int
            L2ABand index.

        Returns
        -------
        List of GeoJSON mappings.
        """
        footprints = self._get_band_mask(band, BandQIMask.detector_footprints)
        if len(footprints) == 0:
            raise MissingAsset(
                f"No detector footprints found for band {band} in {self}"
            )
        return footprints

    def technical_quality_mask(self, band: L2ABand) -> List[Dict]:
        """
        Return technical quality mask.

        Paramerters
        -----------
        band_idx : int
            L2ABand index.

        Returns
        -------
        List of GeoJSON mappings.
        """
        return self._get_band_mask(band, BandQIMask.technical_quality)

    def viewing_incidence_angles(self, band: L2ABand) -> Dict:
        """
        Return viewing incidence angles.

        Paramerters
        -----------
        band_idx : int
            L2ABand index.

        Returns
        -------
        Dictionary of 'zenith' and 'azimuth' angles.
        """
        if self._viewing_incidence_angles_cache.get(band) is None:
            angles: Dict[str, Any] = {
                ViewAngle.zenith: {"detector": dict(), "mean": None},
                ViewAngle.azimuth: {"detector": dict(), "mean": None},
            }
            for grids in self.xml_root.iter("Viewing_Incidence_Angles_Grids"):
                band_idx = int(grids.get("bandId"))
                if band_idx == band.value:
                    detector = int(grids.get("detectorId"))
                    for angle in ViewAngle:
                        raster = _get_grid_data(
                            group=grids,
                            tag=angle.value,
                            bounds=self.bounds,
                            crs=self.crs,
                        )
                        angles[angle]["detector"][detector] = dict(raster=raster)
            for band_angles in self.xml_root.iter("Mean_Viewing_Incidence_Angle_List"):
                for band_angle in band_angles:
                    band_idx = int(band_angle.get("bandId"))
                    if band_idx == band.value:
                        for angle in ViewAngle:
                            angles[angle].update(
                                mean=float(
                                    band_angle.findall(f"{angle.value.upper()}_ANGLE")[
                                        0
                                    ].text
                                )
                            )

            self._viewing_incidence_angles_cache[band] = angles
        return self._viewing_incidence_angles_cache[band]

    def viewing_incidence_angle(
        self, band: L2ABand, detector_id: int, angle: ViewAngle = ViewAngle.zenith
    ) -> Dict:
        return self.viewing_incidence_angles(band)[angle]["detector"][detector_id]

    def mean_viewing_incidence_angles(
        self,
        bands: Union[List[L2ABand], L2ABand, None] = None,
        angle: ViewAngle = ViewAngle.zenith,
        resolution: Resolution = Resolution["120m"],
        resampling="bilinear",
        smoothing_iterations=10,
    ) -> np.ndarray:
        if bands is None:
            bands = list(L2ABand)
        if isinstance(bands, L2ABand):
            bands = [bands]

        def _band_angles(band: L2ABand):
            detector_angles = self.viewing_incidence_angles(band)[angle]["detector"]
            band_angles = ma.masked_equal(
                np.zeros(self.shape(resolution), dtype=np.float32), 0
            )
            # for detector in detectors.values():
            for detector in self.detector_footprints(band):
                detector_id = int(detector["id"])
                # handle rare cases where detector geometries are available but no respective
                # angle arrays:
                if detector_id not in detector_angles:  # pragma: no cover
                    logger.debug(
                        f"no {angle} angles grid found for detector {detector_id}"
                    )
                    continue
                detector_raster = detector_angles[detector_id]["raster"]
                # interpolate missing nodata edges and return BRDF difference model
                detector_raster.data = ma.masked_invalid(
                    fillnodata(
                        detector_raster.data,
                        smoothing_iterations=smoothing_iterations,
                    )
                )
                # resample detector angles to output resolution
                detector_angle = resample_array(
                    in_array=detector_raster.data,
                    in_crs=detector_raster.crs,
                    in_transform=detector_raster.transform,
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

        with Timer() as tt:
            mean = ma.mean(ma.stack([_band_angles(band) for band in bands]), axis=0)
        logger.debug(
            "mean viewing incidence angles for %s bands generated in %s", len(bands), tt
        )
        return mean

    def _get_band_mask(self, band: L2ABand, qi_mask: BandQIMask):
        if self._band_masks_cache.get(qi_mask, {}).get(band) is None:
            mask_path = self.path_mapper.band_qi_mask(qi_mask=qi_mask, band=band)
            if mask_path.suffix == ".jp2":
                features = self._vectorize_raster_mask(mask_path)
                # append detector ID for detector footprints
                if qi_mask == BandQIMask.detector_footprints:
                    for f in features:
                        f["properties"]["detector_id"] = int(
                            f["properties"].pop("value")
                        )
            else:
                features = self._read_vector_mask(mask_path)
                # append detector ID for detector footprints
                if qi_mask == BandQIMask.detector_footprints:
                    for f in features:
                        detector_id = int(f["properties"]["gml_id"].split("-")[-2])
                        f["id"] = detector_id
                        f["properties"]["detector_id"] = detector_id

            self._band_masks_cache[qi_mask][band] = features

        return self._band_masks_cache[qi_mask][band]

    @staticmethod
    def _read_vector_mask(mask_path):
        logger.debug(f"open {mask_path} with Fiona")
        with _cached_path(mask_path) as cached:
            try:
                with fiona_open(cached) as src:
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
                with rasterio_open(cached) as src:
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


@contextmanager
def _cached_path(
    path: MPath, timeout=5, requester_payer="requester", region="eu-central-1"
):
    """If path is remote, download to temporary directory and return path."""
    if path.is_remote():
        with TemporaryDirectory() as tempdir:
            tempfile = MPath(tempdir) / path.name
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
        Resolution["10m"]: {},
        Resolution["20m"]: {},
        Resolution["60m"]: {},
        Resolution["120m"]: {},
    }
    for size in root.iter("Size"):
        resolution = Resolution[f"{size.get('resolution')}m"]
        for item in size:
            if item.tag == "NROWS":
                height = int(item.text)
            elif item.tag == "NCOLS":
                width = int(item.text)
        geoinfo[resolution] = dict(shape=(height, width))
    for geoposition in root.iter("Geoposition"):
        resolution = Resolution[f"{geoposition.get('resolution')}m"]
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
        resolution = Resolution[f"{additional_resolution}m"]
        width_10m, height_10m = geoinfo[Resolution["10m"]]["shape"]
        relation = additional_resolution // 10
        width = width_10m // relation
        height = height_10m // relation
        x_size = geoinfo[Resolution["10m"]]["x_size"] * relation
        y_size = geoinfo[Resolution["10m"]]["y_size"] * relation
        geoinfo[resolution].update(
            shape=(height, width),
            x_size=x_size,
            y_size=y_size,
            transform=from_bounds(left, bottom, right, top, width, height),
        )
    return Bounds(*bounds), geoinfo


def _get_grid_data(group, tag, bounds, crs) -> ReferencedRaster:
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
        left, _, _, top = bounds
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
    return ReferencedRaster(data=grid, transform=affine, bounds=bounds, crs=crs)
