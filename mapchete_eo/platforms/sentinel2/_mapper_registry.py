from typing import List, Callable, Dict, Any, Optional


# decorators for mapper functions using the registry pattern #
##############################################################
ID_MAPPER_REGISTRY: Dict[Any, Callable] = {}
STAC_METADATA_MAPPER_REGISTRY: Dict[Any, Callable] = {}
S2METADATA_MAPPER_REGISTRY: Dict[Any, Callable] = {}

MAPPER_REGISTRIES = {
    "ID": ID_MAPPER_REGISTRY,
    "STAC metadata": STAC_METADATA_MAPPER_REGISTRY,
    "S2Metadata": S2METADATA_MAPPER_REGISTRY,
}


# @dataclass
# class Registries:
#     id_mappers: Dict[Any, Callable] = field(default_factory=dict)
#     stac_metadata_mappers: Dict[Any, Callable] = field(default_factory=dict)
#     s2metadata_mappers: Dict[Any, Callable] = field(default_factory=dict)

#     def register(
#         self,
#         mapper: Literal["ID", "STAC metadata", "S2Metadata"],
#         key: Any,
#         func: Callable,
#     ) -> None:
#         if key in registry:
#             raise ValueError(f"{key} already registered in {registry}")
#         registry[key] = func


# MAPPER_REGISTRY = Registries()


def _register_func(registry: Dict[str, Callable], key: Any, func: Callable):
    if key in registry:
        raise ValueError(f"{key} already registered in {registry}")
    registry[key] = func


def maps_item_id(from_collections: List[str]):
    """
    Decorator registering mapper to common ID.
    """

    def decorator(func):
        # Use a tuple of the metadata as the key
        # key = (path_type, version)
        for collection in from_collections:
            _register_func(registry=ID_MAPPER_REGISTRY, key=collection, func=func)
        return func

    return decorator


def maps_stac_metadata(
    from_collections: List[str], to_data_archives: Optional[List[str]] = None
):
    """
    Decorator registering STAC metadata mapper.
    """

    def decorator(func):
        # Use a tuple of the metadata as the key
        for collection in from_collections:
            if to_data_archives:
                for data_archive in to_data_archives:
                    _register_func(
                        registry=STAC_METADATA_MAPPER_REGISTRY,
                        key=(collection, data_archive),
                        func=func,
                    )
            else:
                _register_func(
                    registry=STAC_METADATA_MAPPER_REGISTRY,
                    key=collection,
                    func=func,
                )
        return func

    return decorator


def creates_s2metadata(from_collections: List[str], to_metadata_archives: List[str]):
    """
    Decorator registering S2Metadata creator.
    """

    def decorator(func):
        # Use a tuple of the metadata as the key
        for collection in from_collections:
            for metadata_archive in to_metadata_archives:
                _register_func(
                    registry=S2METADATA_MAPPER_REGISTRY,
                    key=(collection, metadata_archive),
                    func=func,
                )
        return func

    return decorator
