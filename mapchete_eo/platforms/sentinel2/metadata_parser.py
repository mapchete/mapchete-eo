"""
A metadata parser helps to read additional Sentinel-2 metadata such as
sun angles, quality masks, etc.
"""

import logging
import xml.etree.ElementTree as etree
from functools import cached_property
from typing import Any, Callable, Dict, List, Optional, Union
from xml.etree.ElementTree import Element, ParseError

import numpy as np
import numpy.ma as ma
import pystac
from affine import Affine
from fiona.transform import transform_geom
from mapchete import Timer
from mapchete.io.raster import ReferencedRaster
from mapchete.path import MPath
from mapchete.types import Bounds
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.fill import fillnodata
from rasterio.transform import from_bounds
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from tilematrix import Shape

from mapchete_eo.array.resampling import resample_array
from mapchete_eo.exceptions import CorruptedProductMetadata, MissingAsset
from mapchete_eo.io import open_xml, read_mask_as_raster
from mapchete_eo.platforms.sentinel2.path_mappers import default_path_mapper_guesser
from mapchete_eo.platforms.sentinel2.path_mappers.base import S2PathMapper
from mapchete_eo.platforms.sentinel2.path_mappers.metadata_xml import XMLMapper
from mapchete_eo.platforms.sentinel2.processing_baseline import ProcessingBaseline
from mapchete_eo.platforms.sentinel2.types import (
    BandQI,
    ClassificationBandIndex,
    CloudType,
    L2ABand,
    ProductQI,
    ProductQIMaskResolution,
    Resolution,
    SunAngle,
    ViewAngle,
)
from mapchete_eo.protocols import GridProtocol
from mapchete_eo.types import Grid

logger = logging.getLogger(__name__)


def open_granule_metadata_xml(metadata_xml: MPath) -> Element:
    try:
        return open_xml(metadata_xml)
    except ParseError as exc:
        raise CorruptedProductMetadata(exc)


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
    else:  # pragma: no cover
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
    _cached_xml_root: Optional[etree.Element] = None
    path_mapper_guesser: Callable = default_path_mapper_guesser
    from_stac_item_constructor: Callable = s2metadata_from_stac_item
    crs: CRS
    bounds: Bounds

    def __init__(
        self,
        metadata_xml: MPath,
        path_mapper: S2PathMapper,
        xml_root: Optional[etree.Element] = None,
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
        self._band_masks_cache: Dict[str, dict] = {mask: dict() for mask in BandQI}
        self._l1c_cloud_masks_cache: Optional[List] = None
        self._viewing_incidence_angles_cache: Dict = {}

        # get geoinformation per resolution and bounds
        self.crs = self._crs
        self._grids = _get_grids(self.xml_root, self.crs)
        self.bounds = self._grids[Resolution["10m"]].bounds
        self.footprint = shape(self.bounds)

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
        processing_baseline: Optional[str] = None,
        path_mapper: Optional[S2PathMapper] = None,
        **kwargs,
    ) -> "S2Metadata":
        metadata_xml = MPath.from_inp(metadata_xml, **kwargs)
        xml_root = open_granule_metadata_xml(metadata_xml)
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
            self._cached_xml_root = open_granule_metadata_xml(self.metadata_xml)
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
        for product_qi_mask in ProductQI:
            if product_qi_mask == ProductQI.classification:
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

        for band_qi_mask in BandQI:
            for band in L2ABand:
                out[f"{band_qi_mask.name}-{band.name}"] = self.path_mapper.band_qi_mask(
                    qi_mask=band_qi_mask, band=band
                )

        return out

    def grid(self, resolution: Resolution) -> Grid:
        """
        Return grid for resolution.
        """
        return self._grids[resolution]

    def shape(self, resolution: Resolution) -> Shape:
        """
        Return grid shape for resolution.
        """
        return self._grids[resolution].shape

    def transform(self, resolution: Resolution) -> Affine:
        """
        Return Affine object for resolution.
        """
        return self._grids[resolution].transform

    #####################
    # product QI layers #
    #####################
    def l1c_cloud_mask(
        self,
        cloud_type: CloudType = CloudType.all,
        dst_grid: Union[GridProtocol, Resolution, None] = None,
    ) -> ReferencedRaster:
        """
        Return L1C classification cloud mask.
        """
        dst_grid = dst_grid or Resolution["20m"]
        if isinstance(dst_grid, Resolution):
            dst_grid = self.grid(dst_grid)
        if cloud_type == CloudType.all:
            indexes = [
                ClassificationBandIndex[CloudType.cirrus.name].value,
                ClassificationBandIndex[CloudType.opaque.name].value,
            ]
            cloud_types = [CloudType.cirrus.name, CloudType.opaque.name]
        else:
            indexes = [ClassificationBandIndex[cloud_type.name].value]
            cloud_types = [cloud_type.name]
        return read_mask_as_raster(
            self.path_mapper.classification_mask(),
            indexes=indexes,
            dst_grid=dst_grid,
            rasterize_feature_filter=lambda feature: feature["properties"][
                "maskType"
            ].lower()
            in cloud_types,
            rasterize_value_func=lambda feature: True,
            dtype=bool,
            masked=False,
        )

    def snow_ice_mask(self, dst_grid: Union[GridProtocol, Resolution, None] = None):
        dst_grid = dst_grid or Resolution["20m"]
        if isinstance(dst_grid, Resolution):
            dst_grid = self.grid(dst_grid)
        return read_mask_as_raster(
            self.path_mapper.classification_mask(),
            indexes=[ClassificationBandIndex.snow_ice.value],
            dst_grid=dst_grid,
            rasterize_feature_filter=lambda feature: False,
            rasterize_value_func=lambda feature: True,
            dtype=bool,
            masked=False,
        )

    def cloud_probability(
        self,
        dst_grid: Union[GridProtocol, Resolution, None] = None,
        resampling: Resampling = Resampling.bilinear,
        from_resolution: ProductQIMaskResolution = ProductQIMaskResolution["60m"],
    ) -> ReferencedRaster:
        """Return classification cloud mask."""
        dst_grid = dst_grid or Resolution["20m"]
        if isinstance(dst_grid, Resolution):
            dst_grid = self.grid(dst_grid)
        # TODO: determine whether to read the 20m or the 60m file
        return read_mask_as_raster(
            self.path_mapper.cloud_probability_mask(resolution=from_resolution),
            dst_grid=dst_grid,
            resampling=resampling,
            rasterize_value_func=lambda feature: True,
            masked=False,
        )

    def snow_probability(
        self,
        dst_grid: Union[GridProtocol, Resolution, None] = None,
        resampling: Resampling = Resampling.bilinear,
        from_resolution: ProductQIMaskResolution = ProductQIMaskResolution["60m"],
    ) -> ReferencedRaster:
        """Return classification cloud mask."""
        dst_grid = dst_grid or Resolution["20m"]
        if isinstance(dst_grid, Resolution):
            dst_grid = self.grid(dst_grid)
        # TODO: determine whether to read the 20m or the 60m file
        return read_mask_as_raster(
            self.path_mapper.snow_probability_mask(resolution=from_resolution),
            dst_grid=dst_grid,
            resampling=resampling,
            rasterize_value_func=lambda feature: True,
            masked=False,
        )

    ##############
    # band masks #
    ##############
    def detector_footprints(
        self,
        band: L2ABand,
        dst_grid: Union[GridProtocol, Resolution] = Resolution["60m"],
    ) -> ReferencedRaster:
        """
        Return detector footprints.
        """

        def _get_detector_id(feature) -> int:
            return int(feature["properties"]["gml_id"].split("-")[-2])

        if isinstance(dst_grid, Resolution):
            dst_grid = self.grid(dst_grid)

        footprints = read_mask_as_raster(
            self.path_mapper.band_qi_mask(
                qi_mask=BandQI.detector_footprints, band=band
            ),
            dst_grid=dst_grid,
            rasterize_value_func=_get_detector_id,
        )
        if not footprints.data.any():
            raise MissingAsset(
                f"No detector footprints found for band {band} in {self}"
            )
        return footprints

    def technical_quality_mask(
        self,
        band: L2ABand,
        dst_grid: Union[GridProtocol, Resolution] = Resolution["60m"],
    ) -> ReferencedRaster:
        """
        Return technical quality mask.
        """
        if isinstance(dst_grid, Resolution):
            dst_grid = self.grid(dst_grid)
        return read_mask_as_raster(
            self.path_mapper.band_qi_mask(qi_mask=BandQI.technical_quality, band=band),
            dst_grid=dst_grid,
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
        resampling: Resampling = Resampling.nearest,
        smoothing_iterations: int = 10,
    ) -> np.ndarray:
        bands = list(L2ABand) if bands is None else bands
        bands = [bands] if isinstance(bands, L2ABand) else bands

        def _band_angles(band: L2ABand):
            detector_angles = self.viewing_incidence_angles(band)[angle]["detector"]
            band_angles = ma.masked_equal(
                np.zeros(self.shape(resolution), dtype=np.float32), 0
            )
            detector_footprints = self.detector_footprints(band, dst_grid=resolution)
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
                    grid=self.grid(resolution),
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


def _get_grids(root, crs):
    geoinfo = {
        Resolution["10m"]: dict(crs=crs),
        Resolution["20m"]: dict(crs=crs),
        Resolution["60m"]: dict(crs=crs),
    }
    for size in root.iter("Size"):
        resolution = Resolution[f"{size.get('resolution')}m"]
        for item in size:
            if item.tag == "NROWS":
                height = int(item.text)
            elif item.tag == "NCOLS":
                width = int(item.text)
        geoinfo[resolution].update(height=height, width=width)

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
        geoinfo[resolution].update(
            transform=from_bounds(left, bottom, right, top, width, height),
        )
    out_grids = {k: Grid(**v) for k, v in geoinfo.items()}
    for additional_resolution in [120]:
        resolution = Resolution[f"{additional_resolution}m"]
        grid_10m = out_grids[Resolution["10m"]]
        relation = additional_resolution // 10
        width = grid_10m.width // relation
        height = grid_10m.height // relation
        out_grids[resolution] = Grid(
            from_bounds(left, bottom, right, top, width, height), height, width, crs
        )
    return out_grids


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
