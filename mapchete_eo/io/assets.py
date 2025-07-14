from __future__ import annotations

import logging
import math
from typing import Callable, List, Optional, Union

import fsspec
import numpy as np
import numpy.ma as ma
import pystac
from affine import Affine
from mapchete import Timer
from mapchete.io import copy, fiona_open, rasterio_open
from mapchete.io.raster import ReferencedRaster, read_raster, read_raster_window
from mapchete.path import MPath
from mapchete.protocols import GridProtocol
from mapchete.settings import IORetrySettings
from mapchete.types import Grid, NodataVal
from numpy.typing import DTypeLike
from pydantic import BaseModel
from rasterio.dtypes import dtype_ranges
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.profiles import Profile
from rasterio.vrt import WarpedVRT
from retry import retry

from mapchete_eo.io.path import COMMON_RASTER_EXTENSIONS, asset_mpath, cached_path
from mapchete_eo.io.profiles import COGDeflateProfile

logger = logging.getLogger(__name__)


class STACRasterBandProperties(BaseModel):
    nodata: NodataVal = None
    data_type: Optional[str] = None
    scale: float = 1.0
    offset: float = 0.0

    @staticmethod
    def from_asset(
        asset: pystac.Asset,
        nodataval: NodataVal = None,
    ) -> STACRasterBandProperties:
        if asset.extra_fields.get("raster:offset") is not None:
            properties = dict(
                offset=asset.extra_fields.get("raster:offset"),
                scale=asset.extra_fields.get("raster:scale"),
                nodata=asset.extra_fields.get("nodata", nodataval),
            )
        else:
            properties = asset.extra_fields.get("raster:bands", [{}])[0]
            properties.update(
                nodata=(
                    nodataval
                    if properties.get("nodata") is None
                    else properties.get("nodata")
                ),
            )

        return STACRasterBandProperties(
            **properties,
        )


def asset_to_np_array(
    item: pystac.Item,
    asset: str,
    indexes: Union[List[int], int] = 1,
    grid: Optional[GridProtocol] = None,
    resampling: Resampling = Resampling.nearest,
    nodataval: NodataVal = None,
    apply_offset: bool = True,
) -> ma.MaskedArray:
    """
    Read grid window of STAC Items and merge into a 2D ma.MaskedArray.

    This is the main read method which is one way or the other being called from everywhere
    whenever a band is being read!
    """
    # get path early to catch an eventual asset missing error early
    path = asset_mpath(item, asset)

    # find out asset details if raster:bands is available
    stac_raster_bands = STACRasterBandProperties.from_asset(
        item.assets[asset], nodataval=nodataval
    )

    logger.debug("reading asset %s and indexes %s ...", asset, indexes)
    data = read_raster(
        inp=path,
        indexes=indexes,
        grid=grid,
        resampling=resampling.name,
        dst_nodata=stac_raster_bands.nodata,
    ).data

    if apply_offset and stac_raster_bands.offset:
        data_type = stac_raster_bands.data_type or data.dtype

        # determine value range for the target data_type
        clip_min, clip_max = dtype_ranges[str(data_type)]

        # increase minimum clip value to avoid collission with nodata value
        if clip_min == stac_raster_bands.nodata:
            clip_min += 1

        data[:] = (
            (
                ((data * stac_raster_bands.scale) + stac_raster_bands.offset)
                / stac_raster_bands.scale
            )
            .round()
            .clip(clip_min, clip_max)
            .astype(data_type, copy=False)
            .data
        )

    return data


def get_assets(
    item: pystac.Item,
    assets: List[str],
    dst_dir: MPath,
    src_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
    resolution: Union[None, float, int] = None,
    convert_profile: Optional[Profile] = None,
    item_href_in_dst_dir: bool = True,
    ignore_if_exists: bool = False,
) -> pystac.Item:
    """
    Copy or convert assets depending on settings.

    Conversion is triggered if either resolution or convert_profile is provided.
    """
    for asset in assets:
        path = asset_mpath(item, asset, fs=src_fs)
        # convert if possible
        if should_be_converted(path, resolution=resolution, profile=convert_profile):
            item = convert_asset(
                item,
                asset,
                dst_dir,
                src_fs=src_fs,
                resolution=resolution,
                overwrite=overwrite,
                ignore_if_exists=ignore_if_exists,
                profile=convert_profile or COGDeflateProfile(),
                item_href_in_dst_dir=item_href_in_dst_dir,
            )
            continue

        # copy
        item = copy_asset(
            item,
            asset,
            dst_dir,
            overwrite=overwrite,
            ignore_if_exists=ignore_if_exists,
            item_href_in_dst_dir=item_href_in_dst_dir,
        )

    return item


def copy_asset(
    item: pystac.Item,
    asset: str,
    dst_dir: MPath,
    src_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
    item_href_in_dst_dir: bool = True,
    ignore_if_exists: bool = False,
) -> pystac.Item:
    """Copy asset from one place to another."""
    src_path = asset_mpath(item, asset, fs=src_fs)
    output_path = dst_dir / src_path.name

    # write relative path into asset.href if Item will be in the same directory
    if item_href_in_dst_dir and not output_path.is_absolute():  # pragma: no cover
        item.assets[asset].href = src_path.name
    else:
        item.assets[asset].href = str(output_path)

    # TODO make this check optional
    if output_path.exists():
        if ignore_if_exists:
            logger.debug("ignore existing asset %s", output_path)
            return item
        elif overwrite:
            logger.debug("overwrite exsiting asset %s", output_path)
        else:
            raise IOError(f"{output_path} already exists")
    else:
        dst_dir.makedirs()

    with Timer() as t:
        logger.debug("copy asset %s to %s ...", src_path, dst_dir)
        copy(
            src_path,
            output_path,
            overwrite=overwrite,
        )
    logger.debug("copied asset '%s' in %s", asset, t)

    return item


def convert_asset(
    item: pystac.Item,
    asset: str,
    dst_dir: MPath,
    src_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
    resolution: Union[None, float, int] = None,
    profile: Optional[Profile] = None,
    item_href_in_dst_dir: bool = True,
    ignore_if_exists: bool = False,
) -> pystac.Item:
    """
    Convert asset to a different format.
    """
    src_path = asset_mpath(item, asset, fs=src_fs)
    output_path = dst_dir / src_path.name
    profile = profile or COGDeflateProfile()

    # write relative path into asset.href if Item will be in the same directory
    if item_href_in_dst_dir and not output_path.is_absolute():  # pragma: no cover
        item.assets[asset].href = src_path.name
    else:
        item.assets[asset].href = str(output_path)

    # TODO make this check optional
    if output_path.exists():
        if ignore_if_exists:
            logger.debug("ignore existing asset %s", output_path)
            return item
        elif overwrite:
            logger.debug("overwrite exsiting asset %s", output_path)
        else:
            raise IOError(f"{output_path} already exists")
    else:
        dst_dir.makedirs()

    with Timer() as t:
        convert_raster(src_path, output_path, resolution, profile)
    logger.debug("converted asset '%s' in %s", asset, t)

    return item


@retry(logger=logger, **dict(IORetrySettings()))
def convert_raster(
    src_path: MPath,
    dst_path: MPath,
    resolution: Union[None, float, int] = None,
    profile: Optional[Profile] = None,
) -> None:
    with rasterio_open(src_path, "r") as src:
        meta = src.meta.copy()
        if profile:
            meta.update(**profile)
        src_transform = src.transform
        if resolution:
            logger.debug(
                "converting %s to %s using %sm resolution with profile %s ...",
                src_path,
                dst_path,
                resolution,
                profile,
            )
            src_res = src.transform[0]
            dst_transform = Affine.from_gdal(
                *(
                    src_transform[2],
                    resolution,
                    0.0,
                    src_transform[5],
                    0.0,
                    -resolution,
                )
            )
            dst_width = int(math.ceil(src.width * (src_res / resolution)))
            dst_height = int(math.ceil(src.height * (src_res / resolution)))
            meta.update(
                transform=dst_transform,
                width=dst_width,
                height=dst_height,
            )
        logger.debug("convert %s to %s with settings %s", src_path, dst_path, meta)
        with rasterio_open(dst_path, "w", **meta) as dst:
            with WarpedVRT(
                src,
                width=meta["width"],
                height=meta["height"],
                transform=meta["transform"],
            ) as warped:
                dst.write(warped.read())


def get_metadata_assets(
    item: pystac.Item,
    dst_dir: MPath,
    overwrite: bool = False,
    metadata_parser_classes: Optional[tuple] = None,
    resolution: Union[None, float, int] = None,
    convert_profile: Optional[Profile] = None,
    metadata_asset_names: List[str] = ["metadata", "granule_metadata"],
):
    """Copy STAC item metadata and its metadata assets."""
    for metadata_asset in metadata_asset_names:
        try:
            src_metadata_xml = MPath(item.assets[metadata_asset].href)
            break
        except KeyError:
            pass
    else:  # pragma: no cover
        raise KeyError("no 'metadata' or 'granule_metadata' asset found")

    # copy metadata.xml
    dst_metadata_xml = dst_dir / src_metadata_xml.name
    if overwrite or not dst_metadata_xml.exists():
        copy(src_metadata_xml, dst_metadata_xml, overwrite=overwrite)

    item.assets[metadata_asset].href = src_metadata_xml.name
    if metadata_parser_classes is None:  # pragma: no cover
        raise TypeError("no metadata parser class given")

    for metadata_parser_cls in metadata_parser_classes:
        src_metadata = metadata_parser_cls.from_metadata_xml(src_metadata_xml)
        dst_metadata = metadata_parser_cls.from_metadata_xml(dst_metadata_xml)
        break
    else:  # pragma: no cover
        raise TypeError(
            f"could not parse {src_metadata_xml} with {metadata_parser_classes}"
        )

    # copy assets
    original_asset_paths = src_metadata.assets
    for asset, dst_path in dst_metadata.assets.items():
        src_path = original_asset_paths[asset]

        if overwrite or not dst_path.exists():
            # convert if possible
            if should_be_converted(
                src_path, resolution=resolution, profile=convert_profile
            ):  # pragma: no cover
                convert_raster(src_path, dst_path, resolution, convert_profile)
            else:
                logger.debug("copy %s ...", asset)
                copy(src_path, dst_path, overwrite=overwrite)

    return item


@retry(logger=logger, **dict(IORetrySettings()))
def should_be_converted(
    path: MPath,
    resolution: Union[None, float, int] = None,
    profile: Optional[Profile] = None,
) -> bool:
    """Decide whether a raster file should be converted or not."""
    if path.endswith(tuple(COMMON_RASTER_EXTENSIONS)):
        # see if it even pays off to convert based on resolution
        if resolution is not None:
            with rasterio_open(path) as src:
                src_resolution = src.transform[0]
            if src_resolution != resolution:
                return True

        # when profile is given, check if profile differs from remote file
        elif profile is not None:
            with rasterio_open(path) as src:
                for key, value in profile.items():
                    if value == "COG":
                        # TODO check if file is really a valid cog
                        value = "GTiff"
                    if key in src.meta and src.meta[key] != value:
                        logger.debug(
                            "different value for %s required: %s should become %s",
                            key,
                            src.meta[key],
                            value,
                        )
                        return True
                return False

    return False


def _read_vector_mask(mask_path):
    logger.debug("open %s with Fiona", mask_path)
    with cached_path(mask_path) as cached:
        try:
            with fiona_open(cached) as src:
                return list([dict(f) for f in src])
        except ValueError as e:
            # this happens if GML file is empty
            for message in ["Null layer: ", "'hLayer' is NULL in 'OGR_L_GetName'"]:
                if message in str(e):
                    return []
            else:  # pragma: no cover
                raise


@retry(logger=logger, **dict(IORetrySettings()))
def read_mask_as_raster(
    path: MPath,
    indexes: Optional[List[int]] = None,
    dst_grid: Optional[GridProtocol] = None,
    resampling: Resampling = Resampling.nearest,
    rasterize_value_func: Callable = lambda feature: feature.get("id", 1),
    rasterize_feature_filter: Callable = lambda feature: True,
    dtype: Optional[DTypeLike] = None,
    masked: bool = True,
    cached_read: bool = False,
) -> ReferencedRaster:
    """
    Read mask as array regardless of source data type (raster or vector).
    """
    if dst_grid:
        dst_grid = Grid.from_obj(dst_grid)
    try:
        with cached_path(path, active=cached_read) as path:
            if path.suffix in COMMON_RASTER_EXTENSIONS:
                if dst_grid:
                    array = read_raster_window(
                        path, grid=dst_grid, indexes=indexes, resampling=resampling
                    )
                    # sum up bands to 2D mask and keep dtype
                    array = array.sum(axis=0, dtype=array.dtype)
                    mask = ReferencedRaster(
                        data=array if masked else array.data,
                        transform=dst_grid.transform,
                        bounds=dst_grid.bounds,
                        crs=dst_grid.crs,
                    )
                else:
                    with rasterio_open(path) as src:
                        mask = ReferencedRaster(
                            src.read(indexes, masked=masked).sum(
                                axis=0, dtype=src.dtypes[0]
                            ),
                            transform=src.transform,
                            bounds=src.bounds,
                            crs=src.crs,
                        )

                # make sure output has correct dtype
                if dtype:
                    mask.data = mask.data.astype(dtype)
                return mask

            else:
                if dst_grid:
                    features = [
                        feature
                        for feature in _read_vector_mask(path)
                        if rasterize_feature_filter(feature)
                    ]
                    features_values = [
                        (feature["geometry"], rasterize_value_func(feature))
                        for feature in features
                    ]
                    return ReferencedRaster(
                        data=(
                            rasterize(
                                features_values,
                                out_shape=dst_grid.shape,
                                transform=dst_grid.transform,
                                dtype=np.uint8,
                            ).astype(dtype)
                            if features_values
                            else np.zeros(dst_grid.shape, dtype=dtype)
                        ),
                        transform=dst_grid.transform,
                        crs=dst_grid.crs,
                        bounds=dst_grid.bounds,
                    )
                else:  # pragma: no cover
                    raise ValueError("out_shape and out_transform have to be provided.")
    except Exception as exception:  # pragma: no cover
        # This is a hack because some tool using aiohttp does not raise a
        # ClientResponseError directly but masks it as a generic Exception and thus
        # preventing our retry mechanism to kick in.
        if repr(exception).startswith('Exception("ClientResponseError'):
            raise ConnectionError(repr(exception)).with_traceback(
                exception.__traceback__
            ) from exception
        raise
