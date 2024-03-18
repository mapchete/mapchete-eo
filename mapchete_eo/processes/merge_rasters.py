import logging
from enum import Enum
from typing import Generator, List, Optional, Tuple

import numpy as np
import numpy.ma as ma
from mapchete import Timer
from mapchete.errors import MapcheteNodataTile
from mapchete.formats.base import InputTile
from mapchete.io.vector import to_shape
from mapchete.processing.mp import MapcheteProcess
from mapchete.tile import BufferedTile
from rasterio.features import geometry_mask
from shapely.geometry.base import BaseGeometry

from mapchete_eo.image_operations import filters

logger = logging.getLogger(__name__)


class MergeMethod(str, Enum):
    fill = "fill"
    footprint_gradient = "footprint_gradient"


def execute(
    mp: MapcheteProcess,
    region_group_name: str = "rasters",
    gradient_buffer: int = 10,
    merge_method: MergeMethod = MergeMethod.footprint_gradient,
):
    """
    Merge multiple rasters into one.
    """
    rasters = []
    region_footprints = []

    with Timer() as tt:
        for region_name, region in get_raster_inputs(mp, region_group_name):
            raster = region.read()
            if raster.mask.all():
                logger.debug("%s raster is empty", region_name)
                continue

            rasters.append(raster)
            region_footprints.append(region.area)

    logger.debug("%s rasters created in %s", len(rasters), tt)

    if len(rasters) == 0:
        raise MapcheteNodataTile("no input rasters found")

    with Timer() as tt:
        merged = merge_rasters(
            rasters,
            mp.tile,
            footprints=region_footprints,
            method=merge_method,
            gradient_buffer=gradient_buffer,
        )
    logger.debug("%s mosaics merged in %s", len(rasters), tt)
    return merged


# just for typing
def get_raster_inputs(
    mp: MapcheteProcess, group_name: str = "rasters"
) -> Generator[Tuple[str, InputTile], None, None]:
    for name, raster in mp.open(group_name):
        if raster.is_empty():
            logger.debug("%s is emtpy", name)
        else:
            yield (name, raster)


def merge_rasters(
    rasters: List[ma.MaskedArray],
    tile: BufferedTile,
    method: MergeMethod = MergeMethod.fill,
    footprints: Optional[List[BaseGeometry]] = None,
    gradient_buffer: int = 10,
) -> ma.MaskedArray:
    footprints = footprints or []
    if len(rasters) == 0:
        raise ValueError("no rasters provided")
    elif len(rasters) == 1:
        return rasters[0]

    if method == MergeMethod.fill:
        return fillnodata_merge(rasters)

    elif method == MergeMethod.footprint_gradient:
        if footprints is None:
            raise TypeError(
                "for gradient_merge, a list of footprints has to be provided"
            )
        return gradient_merge(
            rasters=rasters,
            footprints=footprints,
            tile=tile,
            gradient_buffer=gradient_buffer,
        )
    else:  # pragma: no cover
        raise ValueError(f"unkonw merge method '{method}'")


def fillnodata_merge(
    rasters: List[ma.MaskedArray],
) -> ma.MaskedArray:
    """
    Read rasters sequentially and update masked pixels with values of next raster.
    """
    out = ma.empty_like(rasters[0])
    for raster in rasters:
        out[~raster.mask] = raster[~raster.mask]
        out.mask[~raster.mask] = raster.mask[~raster.mask]
        # if output is already full, don't add any further raster data
        if not out.mask.any():
            break
    return out


def gradient_merge(
    rasters: List[ma.MaskedArray],
    footprints: List[BaseGeometry],
    tile: BufferedTile,
    gradient_buffer: int = 10,
) -> ma.MaskedArray:
    """Use footprint geometries to merge rasters using a gradient buffer."""
    if len(footprints) != len(rasters):  # pragma: no cover
        raise ValueError(
            f"footprints ({len(footprints)}) do not match rasters ({len(rasters)}) count"
        )

    out_data = np.zeros(rasters[0].shape, dtype=np.float16)
    out_mask = np.ones(rasters[0].shape, dtype=bool)

    for raster, footprint in zip(rasters, footprints):
        # create gradient mask from footprint
        footprint_mask = geometry_mask(
            [to_shape(footprint)],
            raster.mask[0].shape,
            tile.transform,
            all_touched=False,
            invert=False,
        )

        # TODO: the gaussian_blur function demands a 3-band array, so we have to
        # hack around that. This could be improved.
        gradient_1band = filters.gaussian_blur(
            (~np.stack([footprint_mask for _ in range(3)]) * 255).astype("uint8"),
            radius=gradient_buffer,
        )[0]
        # gradient_1band now has values from 1 (no footprint coverage) to 255 (full
        # footprint coverage)
        # set 1 to 0:
        gradient_1band[gradient_1band == 1] = 0
        logger.debug(f"gradient_1band: {gradient_1band}")

        # extrude array to match number of raster bands
        gradient_8bit = np.stack([gradient_1band for _ in range(raster.shape[0])])
        logger.debug(f"gradient_8bit: {gradient_8bit}")

        # scale gradient from 0 to 1
        gradient = gradient_8bit / 255
        logger.debug(f"gradient: {gradient}")

        # now only apply the gradient where out and raster have values
        # otherwise pick the remaining existing value or keep a masked
        # pixel if both are masked

        # clip raster with end of gradient:
        clip_mask = raster.mask + (gradient_8bit == 0)
        raster.mask = clip_mask

        # the weight array is going to be used to merge the existing output array with
        # current raster
        weight = np.zeros(gradient.shape, dtype=np.float16)

        # set weight values according to the following rules:
        # both values available: use gradient (1 for full raster and 0 for full out)
        weight[~out_mask & ~clip_mask] = gradient[~out_mask & ~clip_mask]
        # only raster data available: 1
        weight[out_mask & ~clip_mask] = 1.0
        # only out data available: 0
        weight[~out_mask & clip_mask] = 0.0
        # none of them available: 0
        weight[out_mask & clip_mask] = 0.0

        # update out mask
        weight_mask = np.zeros(weight.shape, dtype=bool)
        # both values available: False
        # only raster: False
        # only out: False
        # none: True
        weight_mask[out_mask & clip_mask] = True

        # sum of weighted existing data with new data
        out_data[~clip_mask] = (
            # weight existing data
            (out_data[~clip_mask] * (1.0 - weight[~clip_mask]))
            # weight new data
            + (raster[~clip_mask].astype(np.float16) * weight[~clip_mask])
        )
        out_mask[~clip_mask] = weight_mask[~clip_mask]

    return ma.MaskedArray(
        data=out_data.astype(rasters[0].dtype, copy=False), mask=out_mask
    )
