from typing import List, Callable, Dict, Any


# decorators for mapper functions using the registry pattern #
##############################################################
ID_MAPPER_REGISTRY: Dict[Any, Callable] = {}
ASSET_PATHS_MAPPER_REGISTRY: Dict[Any, Callable] = {}
S2METADATA_MAPPER_REGISTRY: Dict[Any, Callable] = {}

MAPPER_REGISTRIES = {
    "ID": ID_MAPPER_REGISTRY,
    "asset paths": ASSET_PATHS_MAPPER_REGISTRY,
    "S2Metadata": S2METADATA_MAPPER_REGISTRY,
}


def _register_func(registry: Dict[str, Callable], key: Any, func: Callable):
    if key in registry:
        raise ValueError(f"{key} already registered in {registry}")
    registry[key] = func


def maps_item_id(from_catalogs: List[str]):
    """
    Decorator registering mapper to common ID.
    """

    def decorator(func):
        # Use a tuple of the metadata as the key
        # key = (path_type, version)
        for catalog in from_catalogs:
            _register_func(registry=ID_MAPPER_REGISTRY, key=catalog, func=func)
        return func

    return decorator


def maps_asset_paths(from_catalogs: List[str], to_data_archives: List[str]):
    """
    Decorator registering asset path mapper.
    """

    def decorator(func):
        # Use a tuple of the metadata as the key
        for catalog in from_catalogs:
            for data_archive in to_data_archives:
                _register_func(
                    registry=ASSET_PATHS_MAPPER_REGISTRY,
                    key=(catalog, data_archive),
                    func=func,
                )
        return func

    return decorator


def creates_s2metadata(from_catalogs: List[str], to_metadata_archives: List[str]):
    """
    Decorator registering S2Metadata creator.
    """

    def decorator(func):
        # Use a tuple of the metadata as the key
        for catalog in from_catalogs:
            for metadata_archive in to_metadata_archives:
                _register_func(
                    registry=S2METADATA_MAPPER_REGISTRY,
                    key=(catalog, metadata_archive),
                    func=func,
                )
        return func

    return decorator
