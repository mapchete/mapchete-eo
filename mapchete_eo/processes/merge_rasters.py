import logging
from enum import Enum
from typing import List, Optional

import numpy as np
import numpy.ma as ma
from mapchete.errors import MapcheteNodataTile
from mapchete.io.vector import to_shape
from mapchete.processing.mp import MapcheteProcess
from mapchete.tile import BufferedTile
from rasterio.features import geometry_mask
from shapely.geometry import base, mapping, shape
from shapely.ops import unary_union

from mapchete_eo.image_operations import filters

logger = logging.getLogger(__name__)


class MergeMethod(str, Enum):
    fill = "fill"
    footprint_gradient = "footprint_gradient"


def execute(
    mp: MapcheteProcess,
    region_rasters_mapping: Optional[dict] = None,
    gradient_buffer: int = 10,
    merge_method: MergeMethod = MergeMethod.footprint_gradient,
):
    """
    Merge multiple rasters into one.

    Parameters
    ----------
    regions_rasters_mapping : dict
        Mapping between region name as provided in the "region" property
        of the "regions" vector input and the input name of the desired raster(s).
        e.g.:
        {
            4mo_north: ["4mo_north"],
            6mo_north: ["6mo_north", "8mo_north"]
        }
        If multiple rasters are given they will be merged using a "fill until full"
        approach.
    gradient_buffer : int
        Buffer of gradient in pixels. (default: 10)

    Returns
    -------
    merged raster : numpy.ma.MaskedArray
    """
    region_rasters_mapping = region_rasters_mapping or {}
    # read region features
    with mp.open("regions") as src:
        if src.is_empty():
            raise MapcheteNodataTile

        regions = src.read()

        # make regions unique in case we have multiple regions with same input raster
        unique_regions: dict = {}
        for r in regions:
            if r["properties"]["region"] not in unique_regions:
                unique_regions[r["properties"]["region"]] = []
            unique_regions[r["properties"]["region"]].append(r)
        regions = [
            features[0]
            if len(regions) == 1
            else dict(
                features[0],
                geometry=mapping(unary_union([shape(f["geometry"]) for f in features])),
            )
            for region_name, features in unique_regions.items()
        ]
        logger.debug(
            f"{len(regions)} unique region(s) over tile: {', '.join([r['properties']['region'] for r in regions])}"
        )

        ## if only one feature, read one raster and return
        if len(regions) == 1:
            region = regions[0]
            region_name = region["properties"]["region"]
            return merge_rasters(
                [mp.open(m).read() for m in region_rasters_mapping[region_name]],
                mp.tile,
            )

        ## if 2 or more features, merge
        else:
            return merge_rasters(
                [
                    merge_rasters(
                        [
                            mp.open(m).read()
                            for m in region_rasters_mapping[
                                region["properties"]["region"]
                            ]
                        ],
                        mp.tile,
                    )
                    for region in regions
                ],
                mp.tile,
                method=merge_method,
                footprints=regions,
                gradient_buffer=gradient_buffer,
            )


def merge_rasters(
    rasters: List[ma.MaskedArray],
    tile: BufferedTile,
    method: MergeMethod = MergeMethod.fill,
    footprints: Optional[List[base.BaseGeometry]] = None,
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
    footprints: List[base.BaseGeometry],
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
