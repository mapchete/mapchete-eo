from abc import ABC
from cached_property import cached_property

from mapchete_eo import models
from mapchete_eo.known_catalogs import EarthSearchV1S2L2A
from mapchete_eo.search.base import Catalog
from mapchete_eo.search.stac_search import STACSearchCatalog
from mapchete_eo.platforms.sentinel2._preprocessing import (
    prepare_product_assets as prepare_s2_product_assets,
)
from mapchete_eo.settings import STAC_ALLOWED_COLLECTIONS

from mapchete_eo.exceptions import InvalidMapcheteEOCollectionError


class DataProduct(ABC):
    def __init__(self, id, **kwargs):
        self.product_model = models.DataProduct
        self.id = id

    @cached_property
    def bbox(self):
        raise NotImplementedError

    @cached_property
    def bounds(self):
        raise NotImplementedError

    @cached_property
    def crs(self):
        raise NotImplementedError

    def get_metadata():
        raise NotImplementedError

    def prepare_product_assets(self):
        if self.platform.lower() == "sentinel2":
            prepare_s2_product_assets(
                product=None,
                config=None,
                requester_payer=None,
                process_bounds=None,
                process_crs=None,
            )


# DataCollection fully compatible with STAC specs
class StacDataCollection(EarthSearchV1S2L2A, STACSearchCatalog, Catalog):
    def __init__(self, collection_name, catalogue=None, data_products=None, **kwargs):
        if collection_name.lower() not in STAC_ALLOWED_COLLECTIONS:
            raise InvalidMapcheteEOCollectionError(
                f"Collection: {collection_name} is not allowed!"
            )

        self.collection = collection_name

        if catalogue is None:
            self.stac_search_catalogue = EarthSearchV1S2L2A(
                collections=self.collection, **kwargs
            )
        # if data_products is None:
        # self._get_data_products_from_search(**kwargs)

    @cached_property
    def _catalogue(self):
        data_products = self.write_static_catalog()
        self._validate_data_collection(data_products)
        return data_products

    def _get_data_products_from_search(self, **kwargs):
        refined_stac_data_products = {}
        search_results = self._search(**kwargs)
        for result in search_results:
            refined_stac_data_products = result
        self._validate_data_collection(refined_stac_data_products)
        return refined_stac_data_products

    def _preprocess_data_products(self):
        raise NotImplementedError

    def _validate_data_collection(self):
        raise NotImplementedError
