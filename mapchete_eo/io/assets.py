import logging
import math
from collections import defaultdict
from typing import Callable, List, Union

import fsspec
import numpy as np
import pystac
from affine import Affine
from mapchete import Timer
from mapchete.io import copy, fiona_open, rasterio_open
from mapchete.io.raster import ReferencedRaster
from mapchete.path import MPath
from mapchete.types import Bounds
from numpy.typing import DTypeLike
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.profiles import Profile
from rasterio.transform import array_bounds
from rasterio.vrt import WarpedVRT
from tilematrix import Shape

from mapchete_eo.array.resampling import resample_array
from mapchete_eo.io.path import COMMON_RASTER_EXTENSIONS, cached_path
from mapchete_eo.io.profiles import COGDeflateProfile
from mapchete_eo.protocols import GridProtocol

logger = logging.getLogger(__name__)


def asset_mpath(
    item: pystac.Item, asset: str, fs: fsspec.AbstractFileSystem = None
) -> MPath:
    """Return MPath instance with asset href."""
    try:
        return MPath(item.assets[asset].href, fs=fs)
    except KeyError:
        raise KeyError(
            f"no asset named '{asset}' found in assets: {', '.join(item.assets.keys())}"
        )


def get_assets(
    item: pystac.Item,
    assets: List[str],
    dst_dir: MPath,
    src_fs: fsspec.AbstractFileSystem = None,
    overwrite: bool = False,
    resolution: Union[None, float, int] = None,
    convert_profile: Union[None, Profile] = None,
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
    profile: Union[Profile, None] = None,
    item_href_in_dst_dir: bool = True,
    ignore_if_exists: bool = False,
) -> pystac.Item:
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


def convert_raster(
    src_path: MPath,
    dst_path: MPath,
    resolution: Union[None, float, int] = None,
    profile: Union[Profile, None] = None,
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


def eo_bands_to_assets_indexes(item: pystac.Item, eo_bands: List[str]) -> List[tuple]:
    """
    Find out location (asset and band index) of EO band.
    """
    mapping = defaultdict(list)
    for eo_band in eo_bands:
        for asset_name, asset in item.assets.items():
            asset_eo_bands = asset.extra_fields.get("eo:bands")
            if asset_eo_bands:
                for band_idx, band_info in enumerate(asset_eo_bands, 1):
                    if eo_band == band_info.get("name"):
                        mapping[eo_band].append((asset_name, band_idx))

    for eo_band in eo_bands:
        if eo_band not in mapping:
            raise KeyError(f"EO band {eo_band} not found in item assets")
        found = mapping[eo_band]
        if len(found) > 1:
            for asset_name, band_idx in found:
                if asset_name == eo_band:
                    mapping[eo_band] = [(asset_name, band_idx)]
                    break
            else:  # pragma: no cover
                raise ValueError(
                    f"EO band {eo_band} found in multiple assets: {', '.join([f[0] for f in found])}"
                )

    return [mapping[eo_band][0] for eo_band in eo_bands]


def get_metadata_assets(
    item: pystac.Item,
    dst_dir: MPath,
    overwrite: bool = False,
    metadata_parser_classes: Union[tuple, None] = None,
    resolution: Union[None, float, int] = None,
    convert_profile: Union[None, Profile] = None,
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
                logger.debug(f"copy {asset} ...")
                copy(src_path, dst_path, overwrite=overwrite)

    return item


def should_be_converted(
    path: MPath,
    resolution: Union[None, float, int] = None,
    profile: Union[None, Profile] = None,
) -> bool:
    """Decide whether a raster file should be converted or not."""
    if path.endswith(tuple(COMMON_RASTER_EXTENSIONS)):
        # see if it even pays off to convert based on resolution
        if resolution is not None:
            with rasterio_open(path) as src:
                src_resolution = src.transform[0]
            if src_resolution != resolution:
                return True

        # when profile is given, convert anyways
        elif profile is not None:
            return True

    return False


def _read_vector_mask(mask_path):
    logger.debug(f"open {mask_path} with Fiona")
    with cached_path(mask_path) as cached:
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


def read_mask_as_raster(
    path: MPath,
    indexes: Union[List[int], None] = None,
    dst_grid: Union[GridProtocol, None] = None,
    rasterize_value_func: Callable = lambda feature: feature.get("id", 1),
    rasterize_feature_filter: Callable = lambda feature: True,
    rasterize_out_dtype: Union[DTypeLike, None] = None,
) -> ReferencedRaster:
    if path.suffix in COMMON_RASTER_EXTENSIONS:
        with rasterio_open(path) as src:
            mask = ReferencedRaster(
                src.read(indexes).sum(axis=0),
                transform=src.transform,
                bounds=src.bounds,
                crs=src.crs,
            )
        if dst_grid:
            mask = ReferencedRaster(
                resample_array(
                    mask,
                    dst_grid,
                    resampling=Resampling.nearest,
                ),
                transform=dst_grid.transform,
                crs=dst_grid.crs,
                bounds=dst_grid.bounds,
            )
        # make sure output has correct dtype
        if rasterize_out_dtype:
            mask.data = mask.data.astype(rasterize_out_dtype)
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
                data=rasterize(
                    features_values,
                    out_shape=dst_grid.shape,
                    transform=dst_grid.transform,
                ).astype(rasterize_out_dtype)
                if features_values
                else np.zeros(dst_grid.shape, dtype=rasterize_out_dtype),
                transform=dst_grid.transform,
                crs=dst_grid.crs,
                bounds=dst_grid.bounds,
            )
        else:  # pragma: no cover
            raise ValueError("out_shape and out_transform have to be provided.")
