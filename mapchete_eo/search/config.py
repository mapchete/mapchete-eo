import logging


from contextlib import contextmanager
from typing import Optional, Dict, Any

from mapchete.path import MPath, MPathLike
from pydantic import BaseModel, model_validator


class StacSearchConfig(BaseModel):
    max_cloud_cover: float = 100.0
    query: Optional[str] = None
    catalog_chunk_threshold: int = 10_000
    catalog_chunk_zoom: int = 5
    catalog_pagesize: int = 100
    footprint_buffer: float = 0

    @model_validator(mode="before")
    def deprecate_max_cloud_cover(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if "max_cloud_cover" in values:  # pragma: no cover
            raise DeprecationWarning(
                "'max_cloud_cover' will be deprecated soon. Please use 'eo:cloud_cover<=...' in the source 'query' field.",
            )
        return values


class StacStaticConfig(BaseModel):
    @model_validator(mode="before")
    def deprecate_max_cloud_cover(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if "max_cloud_cover" in values:  # pragma: no cover
            raise DeprecationWarning(
                "'max_cloud_cover' will be deprecated soon. Please use 'eo:cloud_cover<=...' in the source 'query' field.",
            )
        return values


class UTMSearchConfig(BaseModel):
    @model_validator(mode="before")
    def deprecate_max_cloud_cover(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if "max_cloud_cover" in values:  # pragma: no cover
            raise DeprecationWarning(
                "'max_cloud_cover' will be deprecated soon. Please use 'eo:cloud_cover<=...' in the source 'query' field.",
            )
        return values

    sinergise_aws_collections: dict = dict(
        S2_L2A=dict(
            id="sentinel-s2-l2a",
            path=MPath(
                "https://sentinel-s2-l2a-stac.s3.amazonaws.com/sentinel-s2-l2a.json"
            ),
            endpoint="s3://sentinel-s2-l2a-stac",
        ),
        S2_L1C=dict(
            id="sentinel-s2-l1c",
            path=MPath(
                "https://sentinel-s2-l1c-stac.s3.amazonaws.com/sentinel-s2-l1c.json"
            ),
            endpoint="s3://sentinel-s2-l1c-stac",
        ),
        S1_GRD=dict(
            id="sentinel-s1-l1c",
            path=MPath(
                "https://sentinel-s1-l1c-stac.s3.amazonaws.com/sentinel-s1-l1c.json"
            ),
            endpoint="s3://sentinel-s1-l1c-stac",
        ),
    )
    search_index: Optional[MPathLike] = None


@contextmanager
def patch_invalid_assets():
    """
    Context manager/decorator to fix pystac crash on malformed assets (strings instead of dicts).

    """
    try:
        from pystac.extensions.file import FileExtensionHooks
    except ImportError:  # pragma: no cover
        yield
        return

    logger = logging.getLogger(__name__)

    _original_migrate = FileExtensionHooks.migrate

    def _safe_migrate(self, obj, version, info):
        if "assets" in obj and isinstance(obj["assets"], dict):
            bad_keys = []
            for key, asset in obj["assets"].items():
                if not isinstance(asset, dict):
                    logger.debug(
                        "Removing malformed asset '%s' (type %s) from item %s",
                        key,
                        type(asset),
                        obj.get("id", "unknown"),
                    )
                    bad_keys.append(key)

            for key in bad_keys:
                del obj["assets"][key]

        return _original_migrate(self, obj, version, info)

    # Apply patch
    FileExtensionHooks.migrate = _safe_migrate
    try:
        yield
    finally:
        # Restore original
        FileExtensionHooks.migrate = _original_migrate
