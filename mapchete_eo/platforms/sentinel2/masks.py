import logging
from typing import Iterator, List, Optional

import numpy.ma as ma
import xarray as xr
from mapchete.protocols import GridProtocol

from mapchete_eo.array.convert import to_dataarray, to_masked_array
from mapchete_eo.exceptions import NoSourceProducts
from mapchete_eo.platforms.sentinel2.product import S2Product
from mapchete_eo.platforms.sentinel2.types import Resolution
from mapchete_eo.types import NodataVals

logger = logging.getLogger(__name__)


def read_masks(
    products: List[S2Product],
    grid: Optional[GridProtocol] = None,
    nodatavals: NodataVals = None,
    product_read_kwargs: dict = {},
) -> ma.MaskedArray:
    """Read grid window of Masks and merge into a 4D xarray."""
    return ma.stack(
        [
            to_masked_array(m)
            for m in generate_masks(
                products=products,
                grid=grid,
                nodatavals=nodatavals,
                product_read_kwargs=product_read_kwargs,
            )
        ]
    )


def generate_masks(
    products: List[S2Product],
    grid: Optional[GridProtocol] = None,
    nodatavals: NodataVals = None,
    product_read_kwargs: dict = {},
) -> Iterator[xr.DataArray]:
    """
    Yield masks of slices or products into a cube to support advanced cube handling as Dataarrays.

    This should be analog to other read functions and can be used for read functions
    and read_levelled_cube as input if needed.

    TODO apply these masks on existing cubes (np_arrays, xarrays)
    """
    if len(products) == 0:
        raise NoSourceProducts("no products to read")

    logger.debug(f"reading {len(products)} product masks")

    if isinstance(nodatavals, list):
        nodataval = nodatavals[0]
    elif isinstance(nodatavals, float):
        nodataval = nodatavals
    else:
        nodataval = nodatavals

    product_read_kwargs = dict(
        product_read_kwargs,
        nodatavals=nodatavals,
    )
    for product_ in products:
        if grid is None:
            grid = product_.metadata.grid(Resolution["10m"])
        elif isinstance(grid, Resolution):
            grid = product_.metadata.grid(grid)
        mask_grid = product_.get_mask(
            grid=grid,
            mask_config=product_read_kwargs["mask_config"],
        )
        yield to_dataarray(
            ma.masked_where(mask_grid == 0, ma.expand_dims(mask_grid.data, axis=0)),
            nodataval=nodataval,
            name=product_.id,
            attrs=product_.item.properties,
        )
