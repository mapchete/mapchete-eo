from mapchete.path import MPath
from pystac import Item

from mapchete_eo.platforms.sentinel2._mapper_registry import (
    maps_item_id,
    maps_stac_metadata,
    creates_s2metadata,
)
from mapchete_eo.platforms.sentinel2.preconfigured_sources.metadata_xml_mappers import (
    CDSEPathMapper,
    EarthSearchPathMapper,
    EarthSearchC1PathMapper,
    SinergisePathMapper,
)
from mapchete_eo.platforms.sentinel2.metadata_parser.s2metadata import S2Metadata
from mapchete_eo.search.s2_mgrs import S2Tile


# mapper functions decorated with metadata to have driver decide which one to apply when #
##########################################################################################


@maps_item_id(from_collections=["EarthSearch", "EarthSearch_legacy"])
def earthsearch_id_mapper(item: Item) -> Item:
    item.id = item.properties["s2:product_uri"].rstrip(".SAFE")
    return item


@maps_stac_metadata(from_collections=["EarthSearch"], to_data_archives=["AWSCOG"])
def earthsearch_assets_paths_mapper(item: Item) -> Item:
    """Nothing to do here as paths match catalog."""
    return item


@creates_s2metadata(from_collections=["EarthSearch"], to_metadata_archives=["roda"])
def earthsearch_to_s2metadata(item: Item) -> S2Metadata:
    return S2Metadata.from_stac_item(
        item,
        path_mapper=EarthSearchC1PathMapper(
            MPath(item.assets["granule_metadata"].href)
        ),
        processing_baseline_field="s2:processing_baseline",
    )


@creates_s2metadata(
    from_collections=["EarthSearch_legacy"], to_metadata_archives=["roda"]
)
def earthsearch_legacy_to_s2metadata(item: Item) -> S2Metadata:
    return S2Metadata.from_stac_item(
        item,
        path_mapper=EarthSearchPathMapper(MPath(item.assets["granule_metadata"].href)),
        boa_offset_field="earthsearch:boa_offset_applied",
        processing_baseline_field="s2:processing_baseline",
    )


@maps_item_id(from_collections=["CDSE"])
def plain_id_mapper(item: Item) -> Item:
    return item


CDSE_ASSET_NAME_MAPPING = {
    "AOT_10m": "aot",
    "B01_20m": "coastal",
    "B02_10m": "blue",
    "B03_10m": "green",
    "B04_10m": "red",
    "B05_20m": "rededge1",
    "B06_20m": "rededge2",
    "B07_20m": "rededge3",
    "B08_10m": "nir",
    "B09_60m": "nir09",
    "B11_20m": "swir16",
    "B12_20m": "swir22",
    "B8A_20m": "nir08",
    "SCL_20m": "scl",
    "TCI_10m": "visual",
    "WVP_10m": "wvp",
}


@maps_stac_metadata(from_collections=["CDSE"])
def cdse_asset_names(item: Item) -> Item:
    new_assets = {}
    for asset_name, asset in item.assets.items():
        if asset_name in CDSE_ASSET_NAME_MAPPING:
            asset_name = CDSE_ASSET_NAME_MAPPING[asset_name]
        new_assets[asset_name] = asset

    item.assets = new_assets

    item.properties["s2:datastrip_id"] = item.properties.get("eopf:datastrip_id")
    return item


@maps_stac_metadata(from_collections=["CDSE"], to_data_archives=["AWSJP2"])
def map_cdse_paths_to_jp2_archive(item: Item) -> Item:
    """
    CSDE has the following assets:
    AOT_10m, AOT_20m, AOT_60m, B01_20m, B01_60m, B02_10m, B02_20m, B02_60m, B03_10m, B03_20m,
    B03_60m, B04_10m, B04_20m, B04_60m, B05_20m, B05_60m, B06_20m, B06_60m, B07_20m, B07_60m,
    B08_10m, B09_60m, B11_20m, B11_60m, B12_20m, B12_60m, B8A_20m, B8A_60m, Product, SCL_20m,
    SCL_60m, TCI_10m, TCI_20m, TCI_60m, WVP_10m, WVP_20m, WVP_60m, thumbnail, safe_manifest,
    granule_metadata, inspire_metadata, product_metadata, datastrip_metadata

    sample path for AWS JP2:
    s3://sentinel-s2-l2a/tiles/51/K/XR/2020/7/31/0/R10m/
    """
    if item.datetime is None:
        raise ValueError(f"product {item.get_self_href()} does not have a timestamp")
    path_base_scheme = "s3://sentinel-s2-l2a/tiles/{utm_zone}/{latitude_band}/{grid_square}/{year}/{month}/{day}/{count}"
    s2tile = S2Tile.from_grid_code(item.properties["grid:code"])
    product_basepath = MPath(
        path_base_scheme.format(
            utm_zone=int(s2tile.utm_zone),
            latitude_band=s2tile.latitude_band,
            grid_square=s2tile.grid_square,
            year=item.datetime.year,
            month=item.datetime.month,
            day=item.datetime.day,
            count=0,  # TODO: get count dynamically from metadata
        )
    )
    new_assets = {}
    for asset_name, asset in item.assets.items():
        # ignore these assets
        if asset_name in [
            "Product",
            "safe_manifest",
            "product_metadata",
            "inspire_metadata",
            "datastrip_metadata",
        ]:
            continue
        # set thumbnnail
        elif asset_name == "thumbnail":
            asset.href = str(product_basepath / "R60m" / "TCI.jp2")
        # point to proper metadata
        elif asset_name == "granule_metadata":
            asset.href = str(product_basepath / "metadata.xml")
        # change band asset names and point to their new locations
        elif asset_name in CDSE_ASSET_NAME_MAPPING:
            name, resolution = asset_name.split("_")
            asset.href = product_basepath / f"R{resolution}" / f"{name}.jp2"
            asset_name = CDSE_ASSET_NAME_MAPPING[asset_name]
        else:
            continue
        new_assets[asset_name] = asset

    item.assets = new_assets

    return item


@creates_s2metadata(from_collections=["CDSE"], to_metadata_archives=["CDSE"])
def cdse_s2metadata(item: Item) -> S2Metadata:
    return S2Metadata.from_stac_item(
        item,
        path_mapper=CDSEPathMapper(MPath(item.assets["granule_metadata"].href)),
        processing_baseline_field="processing:version",
    )


@creates_s2metadata(from_collections=["CDSE"], to_metadata_archives=["roda"])
def cdse_to_roda_s2metadata(item: Item) -> S2Metadata:
    return S2Metadata.from_stac_item(
        item,
        path_mapper=SinergisePathMapper(MPath(item.assets["granule_metadata"].href)),
        processing_baseline_field="processing:version",
    )
