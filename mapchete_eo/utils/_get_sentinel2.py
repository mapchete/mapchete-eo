from shapely.geometry import Point, shape
from urllib.parse import urlencode

from mapchete.path import MPath
from mapchete.io._misc import copy as mp_copy

from mapchete_eo.platforms.sentinel2.metadata_parser S2Metadata
from mapchete_eo.platforms.sentinel2.path_mappers import SinergisePathMapper, EarthSearchPathMapper


def get_s2_product(
    metadata_file=None,
    product_id=None,
    bands=None,
    out_path=None,
    resolution=None,
    with_cloudmasks=False,
    with_qi_masks=False,
    overwrite=False,
):
    """Download Sentinel-2 L2A product based on product id or metadata file."""

    if out_path is None:  # pragma: no cover
        raise ValueError("out_dir must be specified")
    else:
        out_path = MPath(out_path)

    if MPath(metadata_file).exists:
        metadata = S2Metadata.from_metadata_xml(
            metadata_xml=MPath(metadata_file),
        )
    elif product_id is not None:
        raise NotImplementedError
    else:
        raise ValueError("Metadata File or Product ID needs to be given!")

    product_id = metadata.product_id

    for band_name in bands:
        band = metadata.bands_dict[band_name]

        if with_cloudmasks:
            raise NotImplementedError
        if with_qi_masks:
            raise NotImplementedError
    breakpoint()



def get_s2_asset(
    is_band=True,
    is_qi_mask=False,
    is_cloudmask=False
):
    raise NotImplementedError

