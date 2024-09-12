from mapchete_eo.product import add_to_blacklist, blacklist_products


def test_blacklist(s2_stac_item, tmp_mpath):
    blacklist_path = tmp_mpath / "blacklist.txt"
    path = s2_stac_item.get_self_href()

    products = blacklist_products(blacklist_path)
    assert len(products) == 0

    add_to_blacklist(path, blacklist_path)
    products = blacklist_products(blacklist_path)
    assert len(products) == 1
    assert path in products

    add_to_blacklist("some_other_path", blacklist_path)
    products = blacklist_products(blacklist_path)
    assert len(products) == 2
