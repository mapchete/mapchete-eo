"""
A metadata parser helps to read additional Sentinel-2 metadata such as
sun angles, quality masks, etc.
"""

import logging
import xml.etree.ElementTree as etree
from contextlib import contextmanager
from functools import cached_property
from tempfile import TemporaryDirectory
from typing import Any, Callable, Dict, List, Union

import numpy as np
import numpy.ma as ma
import pystac
from affine import Affine
from fiona.transform import transform_geom
from mapchete import Timer
from mapchete.io import copy, fiona_open, rasterio_open
from mapchete.io.raster import ReferencedRaster
from mapchete.path import MPath
from mapchete.types import Bounds
from rasterio.crs import CRS
from rasterio.features import rasterize, shapes
from rasterio.fill import fillnodata
from rasterio.transform import array_bounds, from_bounds
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from tilematrix import Shape

from mapchete_eo.array.resampling import resample_array
from mapchete_eo.exceptions import MissingAsset
from mapchete_eo.io import open_xml
from mapchete_eo.io.path import COMMON_RASTER_EXTENSIONS
from mapchete_eo.platforms.sentinel2.path_mappers import default_path_mapper_guesser
from mapchete_eo.platforms.sentinel2.path_mappers.base import S2PathMapper
from mapchete_eo.platforms.sentinel2.path_mappers.metadata_xml import XMLMapper
from mapchete_eo.platforms.sentinel2.processing_baseline import ProcessingBaseline
from mapchete_eo.platforms.sentinel2.types import (
    BandQIMask,
    ClassificationBandIndex,
    CloudType,
    L2ABand,
    ProductQIMask,
    ProductQIMaskResolution,
    Resolution,
    SunAngle,
    ViewAngle,
)

logger = logging.getLogger(__name__)


def _default_from_stac_item_constructor(
    item: pystac.Item,
    **kwargs,
) -> "S2Metadata":
    return S2Metadata.from_metadata_xml(
        metadata_xml=item.assets["metadata"].href,
        **kwargs,
    )


def s2metadata_from_stac_item(
    item: pystac.Item,
    metadata_assets: Union[List[str], str] = ["metadata", "granule_metadata"],
    boa_offset_fields: Union[List[str], str] = [
        "sentinel:boa_offset_applied",
        "earthsearch:boa_offset_applied",
    ],
    processing_baseline_field: str = "s2:processing_baseline",
    **kwargs,
) -> "S2Metadata":
    """Custom code to initialize S2Metadata from a STAC item.

    Depending on from which catalog the STAC item comes, this function should correctly
    set all custom flags such as BOA offsets or pass on the correct path to the metadata XML
    using the proper asset name.
    """
    metadata_assets = (
        [metadata_assets] if isinstance(metadata_assets, str) else metadata_assets
    )
    for metadata_asset in metadata_assets:
        if metadata_asset in item.assets:
            metadata_path = MPath(item.assets[metadata_asset].href)
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

    if metadata_path.is_remote() or metadata_path.is_absolute():
        metadata_xml = metadata_path
    else:
        metadata_xml = MPath(item.self_href).parent / metadata_path

    return S2Metadata.from_metadata_xml(
        metadata_xml=metadata_xml,
        processing_baseline=item.properties.get(processing_baseline_field),
        boa_offset_applied=boa_offset_applied,
        **kwargs,
    )


class S2Metadata:
    _cached_xml_root = None
    path_mapper_guesser: Callable = default_path_mapper_guesser
    from_stac_item_constructor: Callable = s2metadata_from_stac_item
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
    def from_stac_item(cls, item: pystac.Item, **kwargs) -> "S2Metadata":
        return cls.from_stac_item_constructor(item, **kwargs)

    @cached_property
    def xml_root(self):
        if self._cached_xml_root is None:  # pragma: no cover
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
            if product_qi_mask == ProductQIMask.classification:
                out[product_qi_mask.name] = self.path_mapper.product_qi_mask(
                    product_qi_mask
                )
            else:
                for resolution in ProductQIMaskResolution:
                    out[
                        f"{product_qi_mask.name}-{resolution.name}"
                    ] = self.path_mapper.product_qi_mask(
                        product_qi_mask, resolution=resolution
                    )

        for band_qi_mask in BandQIMask:
            for band in L2ABand:
                out[f"{band_qi_mask.name}-{band.name}"] = self.path_mapper.band_qi_mask(
                    qi_mask=band_qi_mask, band=band
                )

        return out

    def shape(self, resolution: Resolution) -> Shape:
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
                for f in _vectorize_raster_mask(
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
                features = _read_vector_mask(mask_path)
            self._cloud_masks_cache = features
        return [
            f
            for f in self._cloud_masks_cache
            if f["properties"]["maskType"].lower() in mask_types_strings
        ]

    def detector_footprints(
        self, band: L2ABand, rasterize_resolution: Resolution = Resolution["60m"]
    ) -> ReferencedRaster:
        """
        Return detector footprints.
        """

        def _get_detector_id(feature) -> int:
            return int(feature["properties"]["gml_id"].split("-")[-2])

        footprints = read_mask_as_raster(
            self.path_mapper.band_qi_mask(
                qi_mask=BandQIMask.detector_footprints, band=band
            ),
            out_crs=self.crs,
            out_shape=self.shape(rasterize_resolution),
            out_transform=self.transform(rasterize_resolution),
            rasterize_value_func=_get_detector_id,
        )
        if not footprints.data.any():
            raise MissingAsset(
                f"No detector footprints found for band {band} in {self}"
            )
        return footprints

    def technical_quality_mask(
        self, band: L2ABand, rasterize_resolution: Resolution = Resolution["60m"]
    ) -> ReferencedRaster:
        """
        Return technical quality mask.
        """
        return read_mask_as_raster(
            self.path_mapper.band_qi_mask(
                qi_mask=BandQIMask.technical_quality, band=band
            ),
            out_crs=self.crs,
            out_shape=self.shape(rasterize_resolution),
            out_transform=self.transform(rasterize_resolution),
        )

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
        resampling: str = "bilinear",
        smoothing_iterations: int = 10,
    ) -> np.ndarray:
        if bands is None:
            bands = list(L2ABand)
        if isinstance(bands, L2ABand):
            bands = [bands]

        def _band_angles(band: L2ABand):
            detector_angles = self.viewing_incidence_angles(band)[angle]["detector"]
            band_angles = ma.masked_equal(
                np.zeros(self.shape(resolution), dtype=np.float16), 0
            )
            detector_footprints = self.detector_footprints(
                band, rasterize_resolution=resolution
            )
            detector_ids = [x for x in np.unique(detector_footprints.data) if x != 0]

            for detector_id in detector_ids:
                # handle rare cases where detector geometries are available but no respective
                # angle arrays:
                if detector_id not in detector_angles:  # pragma: no cover
                    logger.debug(
                        f"no {angle} angles grid found for detector {detector_id}"
                    )
                    continue
                detector_angles_raster = detector_angles[detector_id]["raster"]
                # interpolate missing nodata edges and return BRDF difference model
                detector_angles_raster.data = ma.masked_invalid(
                    fillnodata(
                        detector_angles_raster.data,
                        smoothing_iterations=smoothing_iterations,
                    )
                )
                # resample detector angles to output resolution
                detector_angle = resample_array(
                    detector_angles_raster,
                    nodata=0,
                    dst_transform=self.transform(resolution),
                    dst_crs=self.crs,
                    dst_shape=self.shape(resolution),
                    resampling=resampling,
                )
                # select pixels which are covered by detector
                detector_mask = np.where(
                    detector_footprints.data == detector_id, True, False
                )
                if len(detector_footprints.data.shape) == 3:
                    detector_mask = detector_mask[0]
                # merge detector stripes
                band_angles[detector_mask] = detector_angle[detector_mask]
                band_angles.mask[detector_mask] = detector_angle.mask[detector_mask]

            return band_angles

        with Timer() as tt:
            mean = ma.mean(ma.stack([_band_angles(band) for band in bands]), axis=0)
        logger.debug(
            "mean viewing incidence angles for %s bands generated in %s", len(bands), tt
        )
        return mean

    def _read_mask_as_vector(self, band: L2ABand, qi_mask: BandQIMask) -> dict:
        if self._band_masks_cache.get(qi_mask, {}).get(band) is None:
            mask_path = self.path_mapper.band_qi_mask(qi_mask=qi_mask, band=band)
            if mask_path.suffix == ".jp2":
                features = _vectorize_raster_mask(mask_path)
                # append detector ID for detector footprints
                if qi_mask == BandQIMask.detector_footprints:
                    for f in features:
                        f["properties"]["detector_id"] = int(
                            f["properties"].pop("value")
                        )
            else:
                features = _read_vector_mask(mask_path)
                # append detector ID for detector footprints
                if qi_mask == BandQIMask.detector_footprints:
                    for f in features:
                        detector_id = int(f["properties"]["gml_id"].split("-")[-2])
                        f["id"] = detector_id
                        f["properties"]["detector_id"] = detector_id

            self._band_masks_cache[qi_mask][band] = features

        return self._band_masks_cache[qi_mask][band]


def default_rasterize_value_func(feature):
    return feature["id"]


def read_mask_as_raster(
    path: MPath,
    out_shape: Union[Shape, None] = None,
    out_transform: Union[Affine, None] = None,
    out_crs: Union[CRS, None] = None,
    rasterize_value_func: Callable = default_rasterize_value_func,
) -> ReferencedRaster:
    if path.suffix in COMMON_RASTER_EXTENSIONS:
        mask = ReferencedRaster.from_file(path)
        if out_shape and out_transform:
            return ReferencedRaster(
                resample_array(
                    mask,
                    dst_transform=out_transform,
                    dst_crs=out_crs,
                    dst_shape=out_shape,
                    resampling="nearest",
                ),
                transform=out_transform,
                crs=out_crs,
                bounds=Bounds(
                    array_bounds(out_shape.height, out_shape.width, out_transform)
                ),
            )
        else:
            return mask

    else:
        if out_shape and out_transform:
            features_values = [
                (feature["geometry"], rasterize_value_func(feature))
                for feature in _read_vector_mask(path)
            ]
            return ReferencedRaster(
                data=rasterize(
                    features_values, out_shape=out_shape, transform=out_transform
                )
                if features_values
                else np.zeros(out_shape, dtype=np.uint8),
                transform=out_transform,
                crs=out_crs,
                bounds=Bounds(
                    array_bounds(out_shape.height, out_shape.width, out_transform)
                ),
            )
        else:  # pragma: no cover
            raise ValueError("out_shape and out_transform have to be provided.")


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
            ) == "Null layer: ''" or "'hLayer' is NULL in 'OGR_L_GetName'" in str(e):
                return []
            else:  # pragma: no cover
                raise


# TODO: do we need this?
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
        geoinfo[resolution] = dict(shape=Shape(height, width))
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
            shape=Shape(height, width),
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
