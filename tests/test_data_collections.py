from mapchete_eo.platforms.base import StacDataCollection


def test_data_collection_creation(e84_cog_catalog):
    data_collection = StacDataCollection(
        collection_name='sentinel-2-l2a', kwargs=e84_cog_catalog
    )
    print(data_collection.stac_search_catalogue.bounds)
