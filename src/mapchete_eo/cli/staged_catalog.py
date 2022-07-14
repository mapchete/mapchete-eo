from pystac import Extent
from pystac.collection import Collection


def create_staged_catalog(catalog):
    # catalog = STACSearchCatalog(collections=[collection], **kwargs)
    coll = catalog.client.get_collection(catalog.collection)
    new_coll = Collection(
        id=coll.id,
        extent=Extent(spatial=[], temporal=[]),
        description=coll.description,
        title=coll.title,
        stac_extensions=coll.stac_extensions,
        license=coll.license,
        keywords=coll.keywords,
        providers=coll.providers,
        summaries=coll.summaries,
        extra_fields=coll.extra_fields,
    )
    for item in catalog.items:
        new_coll.add_item(item)
    new_coll.update_extent_from_items()
