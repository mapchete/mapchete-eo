import logging
import warnings
from typing import Any, Dict, List, Tuple, Union

import numpy as np
import numpy.ma as ma
import rasterio
from mapchete import Timer
from mapchete.errors import MapcheteIOError
from mapchete.io.raster import (
    ReferencedRaster,
    _extract_filenotfound_exception,
    _prepare_masked,
    rasterio_open,
)
from mapchete.io.settings import IORetrySettings
from mapchete.path import MPath
from mapchete.tile import BufferedTile
from numpy.typing import DTypeLike
from rasterio.enums import Resampling
from rasterio.errors import RasterioIOError
from rasterio.transform import from_bounds as affine_from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.warp import reproject
from retry import retry
from tilematrix import clip_geometry_to_srs_bounds

from mapchete_eo.protocols import GridProtocol
from mapchete_eo.types import NodataVal

logger = logging.getLogger(__name__)

MPathLike = Union[str, MPath]


def read_raster_window(
    input_files: Union[MPathLike, List[MPathLike]],
    grid: GridProtocol,
    indexes: Union[int, List[int], None] = None,
    resampling: Resampling = Resampling.nearest,
    src_nodata: NodataVal = None,
    dst_nodata: NodataVal = None,
    dst_dtype: Union[DTypeLike, None] = None,
    gdal_opts: Union[dict, None] = None,
    skip_missing_files: bool = False,
) -> ma.MaskedArray:
    """
    Return NumPy array from one or multiple input raster merged into one grid.

    This is based on and a temporary re-implementation of mapchete.io.raster.read_raster_window()
    """
    paths_list = [
        MPath.from_inp(input_file)
        for input_file in (
            input_files if isinstance(input_files, list) else [input_files]
        )
    ]
    if len(paths_list) == 0:  # pragma: no cover
        raise ValueError("no input given")
    try:
        with paths_list[0].rio_env(gdal_opts) as env:
            logger.debug(
                "reading %s file(s) with GDAL options %s", len(paths_list), env.options
            )
            return _read_raster_window(
                paths_list,
                grid,
                indexes=indexes,
                resampling=resampling,
                src_nodata=src_nodata,
                dst_nodata=dst_nodata,
                dst_dtype=dst_dtype,
                skip_missing_files=skip_missing_files,
            )
    except FileNotFoundError:  # pragma: no cover
        raise
    except Exception as e:  # pragma: no cover
        logger.exception(e)
        raise MapcheteIOError(e)


def _read_raster_window(
    paths_list: List[MPath],
    grid: GridProtocol,
    indexes: Union[int, List[int], None] = None,
    resampling: Resampling = Resampling.nearest,
    src_nodata: NodataVal = None,
    dst_nodata: NodataVal = None,
    dst_dtype: Union[DTypeLike, None] = None,
    skip_missing_files: bool = False,
):
    def _empty_array():
        if indexes is None:  # pragma: no cover
            raise ValueError(
                "output shape cannot be determined because no given input files "
                "exist and no band indexes are given"
            )
        dst_shape = (
            (len(indexes), grid.height, grid.width)
            if isinstance(indexes, list)
            else (grid.height, grid.width)
        )
        return ma.masked_array(
            data=np.full(
                dst_shape,
                src_nodata if dst_nodata is None else dst_nodata,
                dtype=dst_dtype,
            ),
            mask=True,
        )

    if len(paths_list) > 1:
        # in case multiple input files are given, merge output into one array
        # using the default rasterio behavior, create a 2D array if only one band
        # is read and a 3D array if multiple bands are read
        dst_array = None
        # read files and add one by one to the output array
        for ff in paths_list:
            try:
                f_array = _read_raster_window(
                    [ff],
                    grid=grid,
                    indexes=indexes,
                    resampling=resampling,
                    src_nodata=src_nodata,
                    dst_nodata=dst_nodata,
                )
                if dst_array is None:
                    dst_array = f_array
                else:
                    dst_array[~f_array.mask] = f_array.data[~f_array.mask]
                    dst_array.mask[~f_array.mask] = False
                    logger.debug("added to output array")
            except FileNotFoundError:
                if skip_missing_files:
                    logger.debug("skip missing file %s", ff)
                else:  # pragma: no cover
                    raise
        if dst_array is None:
            dst_array = _empty_array()
        return dst_array
    else:
        input_file = paths_list[0]
        try:
            dst_shape: Tuple[Any, int, int]
            if isinstance(indexes, int):
                dst_shape = (1, grid.height, grid.width)
            elif indexes is None:
                dst_shape = (None, grid.height, grid.width)
            elif isinstance(indexes, list):
                dst_shape = (len(indexes), grid.height, grid.width)
            # Check if potentially tile boundaries exceed tile matrix boundaries on
            # the antimeridian, the northern or the southern boundary.
            if (
                isinstance(grid, BufferedTile)
                and grid.tp.is_global
                and grid.pixelbuffer
                and grid.is_on_edge()
            ):
                return _get_warped_edge_array(
                    tile=grid,
                    input_file=input_file,
                    indexes=indexes,
                    dst_shape=dst_shape,
                    resampling=resampling,
                    src_nodata=src_nodata,
                    dst_nodata=dst_nodata,
                )

            # If tile boundaries don't exceed pyramid boundaries, simply read window
            # once.
            else:
                return _get_warped_array(
                    input_file=input_file,
                    indexes=indexes,
                    dst_bounds=grid.bounds,
                    dst_shape=dst_shape,
                    dst_crs=grid.crs,
                    resampling=resampling,
                    src_nodata=src_nodata,
                    dst_nodata=dst_nodata,
                )
        except FileNotFoundError:  # pragma: no cover
            if skip_missing_files:
                logger.debug("skip missing file %s", input_file)
                return _empty_array()
            else:
                raise
        except Exception as exc:  # pragma: no cover
            raise OSError(f"failed to read {input_file}") from exc


def _get_warped_edge_array(
    tile: BufferedTile = None,
    input_file: MPath = None,
    indexes=None,
    dst_shape=None,
    resampling=None,
    src_nodata=None,
    dst_nodata=None,
):
    tile_boxes = clip_geometry_to_srs_bounds(
        tile.bbox, tile.tile_pyramid, multipart=True
    )
    parts_metadata: Dict = dict(left=None, middle=None, right=None, none=None)
    # Split bounding box into multiple parts & request each numpy array
    # separately.
    for polygon in tile_boxes:
        # Check on which side the antimeridian is touched by the polygon:
        # "left", "middle", "right"
        # "none" means, the tile touches the edge just on the top and/or
        # bottom boundary
        part_metadata: Dict[str, Any] = {}
        left, bottom, right, top = polygon.bounds
        touches_right = left == tile.tile_pyramid.left
        touches_left = right == tile.tile_pyramid.right
        touches_both = touches_left and touches_right
        height = int(round((top - bottom) / tile.pixel_y_size))
        width = int(round((right - left) / tile.pixel_x_size))
        if indexes is None:
            dst_shape = (None, height, width)
        elif isinstance(indexes, int):
            dst_shape = (height, width)
        else:
            dst_shape = (dst_shape[0], height, width)
        part_metadata.update(bounds=polygon.bounds, shape=dst_shape)
        if touches_both:
            parts_metadata.update(middle=part_metadata)
        elif touches_left:
            parts_metadata.update(left=part_metadata)
        elif touches_right:
            parts_metadata.update(right=part_metadata)
        else:
            parts_metadata.update(none=part_metadata)
    # Finally, stitch numpy arrays together into one. Axis -1 is the last axis
    # which in case of rasterio arrays always is the width (West-East).
    return ma.concatenate(
        [
            _get_warped_array(
                input_file=input_file,
                indexes=indexes,
                dst_bounds=parts_metadata[part]["bounds"],
                dst_shape=parts_metadata[part]["shape"],
                dst_crs=tile.crs,
                resampling=resampling,
                src_nodata=src_nodata,
                dst_nodata=dst_nodata,
            )
            for part in ["none", "left", "middle", "right"]
            if parts_metadata[part]
        ],
        axis=-1,
    )


def _get_warped_array(
    input_file=None,
    indexes=None,
    dst_bounds=None,
    dst_shape=None,
    dst_crs=None,
    resampling=None,
    src_nodata=None,
    dst_nodata=None,
):
    """Extract a numpy array from a raster file."""
    try:
        return _rasterio_read(
            input_file=input_file,
            indexes=indexes,
            dst_bounds=dst_bounds,
            dst_shape=dst_shape,
            dst_crs=dst_crs,
            resampling=resampling,
            src_nodata=src_nodata,
            dst_nodata=dst_nodata,
        )
    except FileNotFoundError:
        raise
    except Exception as e:
        logger.exception("error while reading file %s: %s", input_file, e)
        raise


@retry(logger=logger, exceptions=RasterioIOError, **dict(IORetrySettings()))
def _rasterio_read(
    input_file=None,
    indexes=None,
    dst_bounds=None,
    dst_shape=None,
    dst_crs=None,
    resampling=None,
    src_nodata=None,
    dst_nodata=None,
):
    def _read(
        src, indexes, dst_bounds, dst_shape, dst_crs, resampling, src_nodata, dst_nodata
    ):
        height, width = dst_shape[-2:]
        if indexes is None:
            dst_shape = (len(src.indexes), height, width)
            indexes = list(src.indexes)
        src_nodata = src.nodata if src_nodata is None else src_nodata
        dst_nodata = src.nodata if dst_nodata is None else dst_nodata
        dst_left, dst_bottom, dst_right, dst_top = dst_bounds
        if src.transform.is_identity and src.gcps:
            # no idea why when reading a source referenced using GCPs requires using reproject()
            # instead of WarpedVRT
            return _prepare_masked(
                reproject(
                    source=rasterio.band(src, indexes),
                    destination=np.zeros(dst_shape, dtype=src.meta.get("dtype")),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    src_nodata=src_nodata,
                    dst_transform=affine_from_bounds(
                        dst_left, dst_bottom, dst_right, dst_top, width, height
                    ),
                    dst_crs=dst_crs,
                    dst_nodata=dst_nodata,
                    resampling=Resampling[resampling],
                )[0],
                masked=True,
                nodata=dst_nodata,
            )
        else:
            with WarpedVRT(
                src,
                crs=dst_crs,
                src_nodata=src_nodata,
                nodata=dst_nodata,
                width=width,
                height=height,
                transform=affine_from_bounds(
                    dst_left, dst_bottom, dst_right, dst_top, width, height
                ),
                resampling=Resampling[resampling],
            ) as vrt:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    return vrt.read(
                        window=vrt.window(*dst_bounds),
                        out_shape=dst_shape,
                        indexes=indexes,
                        masked=True,
                    )

    try:
        with Timer() as t:
            with rasterio_open(input_file, "r") as src:
                logger.debug("read from %s...", input_file)
                out = _read(
                    src,
                    indexes,
                    dst_bounds,
                    dst_shape,
                    dst_crs,
                    resampling,
                    src_nodata,
                    dst_nodata,
                )
        logger.debug("read %s in %s", input_file, t)
        return out
    except RasterioIOError as rio_exc:
        _extract_filenotfound_exception(rio_exc, input_file)


def read_raster(
    inp: MPathLike, grid: Union[GridProtocol, None] = None, **kwargs
) -> ReferencedRaster:
    inp = MPath.from_inp(inp)
    logger.debug("reading %s into memory", str(inp))
    if grid:
        # if grid is a tile, we need to wrap it to get the transform attribute
        if isinstance(grid, BufferedTile):
            transform = grid.affine
        else:
            transform = grid.transform
        return ReferencedRaster(
            data=read_raster_window(inp, grid=grid, **kwargs),
            affine=transform,
            bounds=grid.bounds,
            crs=grid.crs,
        )
    with rasterio_open(inp, "r") as src:
        return ReferencedRaster(
            data=src.read(masked=True),
            affine=src.transform,
            bounds=src.bounds,
            crs=src.crs,
        )
