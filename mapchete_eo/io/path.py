import hashlib
import logging
import xml.etree.ElementTree as etree
from contextlib import contextmanager
from enum import Enum
from tempfile import TemporaryDirectory

import pystac
from fsspec.exceptions import FSTimeoutError
from mapchete.io import copy
from mapchete.io.settings import IORetrySettings
from mapchete.path import MPath
from retry import retry

logger = logging.getLogger(__name__)


COMMON_RASTER_EXTENSIONS = [".tif", ".jp2"]


@retry(
    logger=logger,
    exceptions=(TimeoutError, FSTimeoutError),
    **dict(IORetrySettings()),
)
def open_xml(path: MPath):
    logger.debug(f"open {path}")
    return etree.fromstring(path.read_text())


class ProductPathGenerationMethod(str, Enum):
    """Option to generate product cache path."""

    # <cache_basepath>/<product-id>
    product_id = "product_id"

    # <cache_basepath>/<product-hash>
    hash = "hash"

    # <cache_basepath>/<product-day>/<product-month>/<product-year>/<product-id>
    date_day_first = "date_day_first"

    # <cache_basepath>/<product-year>/<product-month>/<product-day>/<product-id>
    date_year_first = "date_year_first"


def get_product_cache_path(
    item: pystac.Item,
    basepath: MPath,
    path_generation_method: ProductPathGenerationMethod = ProductPathGenerationMethod.product_id,
) -> MPath:
    """
    Create product path with high cardinality prefixes optimized for S3.

    product_path_generation option:

    "product_id":
    <cache_basepath>/<product-id>

    "product_hash":
    <cache_basepath>/<product-hash>

    "date_day_first":
    <cache_basepath>/<product-day>/<product-month>/<product-year>/<product-id>

    "date_year_first":
    <cache_basepath>/<product-year>/<product-month>/<product-day>/<product-id>
    """
    path_generation_method = ProductPathGenerationMethod[path_generation_method]
    if path_generation_method == ProductPathGenerationMethod.product_id:
        return basepath / item.id

    elif path_generation_method == ProductPathGenerationMethod.hash:
        return basepath / hashlib.md5(f"{item.id}".encode()).hexdigest()

    else:
        if item.datetime is None:
            raise AttributeError(f"stac item must have a valid datetime object: {item}")
        elif path_generation_method == ProductPathGenerationMethod.date_day_first:
            return (
                basepath
                / item.datetime.day
                / item.datetime.month
                / item.datetime.year
                / item.id
            )

        elif path_generation_method == ProductPathGenerationMethod.date_year_first:
            return (
                basepath
                / item.datetime.year
                / item.datetime.month
                / item.datetime.day
                / item.id
            )


def path_in_paths(path, existing_paths) -> bool:
    """Check if path is contained in list of existing paths independent of path prefix."""
    if path.startswith("s3://"):
        return path.lstrip("s3://") in existing_paths
    else:
        for existing_path in existing_paths:
            if existing_path.endswith(path):
                return True
        else:
            return False


@contextmanager
def cached_path(path: MPath) -> MPath:
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


def absolute_asset_path(item: pystac.Item, asset: str) -> MPath:
    item_dir = MPath.from_inp(item.get_self_href()).parent
    asset_path = MPath(item.assets[asset].href)
    return asset_path.absolute_path(item_dir)
