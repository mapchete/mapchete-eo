import numpy.ma as ma
import pytest
import xarray as xr
from mapchete.formats import available_input_formats
from mapchete.path import MPath
from pytest_lazyfixture import lazy_fixture

from mapchete_eo.array.convert import to_masked_array
from mapchete_eo.exceptions import EmptyStackException, NoSourceProducts
from mapchete_eo.platforms.sentinel2.config import (
    BRDFConfig,
    MaskConfig,
    SceneClassification,
    Sentinel2DriverConfig,
)
from mapchete_eo.product import eo_bands_to_assets_indexes
from mapchete_eo.sort import TargetDateSort


def test_format_available():
    assert "Sentinel-2" in available_input_formats()


def test_config():
    conf = Sentinel2DriverConfig(
        format="Sentinel-2",
        time=dict(
            start="2022-04-01",
            end="2022-04-10",
        ),
    )
    assert conf.model_dump()


def test_jp2_config():
    conf = Sentinel2DriverConfig(
        format="Sentinel-2",
        archive="S2AWS_JP2",
        time=dict(
            start="2022-04-01",
            end="2022-04-10",
        ),
    )
    assert conf.model_dump()


def test_s2_eo_bands_to_assets_indexes(s2_stac_item):
    eo_bands = ["red", "green", "blue"]
    assets_indexes = eo_bands_to_assets_indexes(s2_stac_item, eo_bands)
    assert len(eo_bands) == len(assets_indexes)
    for eo_band, (asset, index) in zip(eo_bands, assets_indexes):
        assert eo_band == asset
        assert index == 1


def test_s2_eo_bands_to_assets_indexes_invalid_band(s2_stac_item):
    eo_bands = ["foo"]
    with pytest.raises(KeyError):
        eo_bands_to_assets_indexes(s2_stac_item, eo_bands)


@pytest.mark.remote
def test_s2_jp2_band_paths(stac_item_sentinel2_jp2):
    eo_bands = ["red", "green", "blue", "nir08"]
    assets_indexes = eo_bands_to_assets_indexes(stac_item_sentinel2_jp2, eo_bands)
    assert len(eo_bands) == len(assets_indexes)
    for eo_band, (asset, index) in zip(eo_bands, assets_indexes):
        assert eo_band == asset
        assert index == 1
        assert MPath(stac_item_sentinel2_jp2.assets[asset].href).exists()


@pytest.mark.remote
def test_remote_s2_read_xarray(sentinel2_mapchete):
    with sentinel2_mapchete.process_mp().open("inp") as cube:
        assert isinstance(cube.read(assets=["coastal"]), xr.Dataset)


@pytest.mark.remote
def test_s2_time_ranges(sentinel2_time_ranges_mapchete):
    with sentinel2_time_ranges_mapchete.process_mp().open("inp") as cube:
        some_in_first = False
        some_in_second = True
        for product in cube.products:
            first, second = cube.time
            within_first = first.start < product.item.datetime.date() < first.end
            within_second = second.start < product.item.datetime.date() < second.end
            if within_first:
                some_in_first = True
            elif within_second:
                some_in_second = True
            else:
                raise ValueError("product outside of given time ranges")
        assert some_in_first
        assert some_in_second


@pytest.mark.remote
def test_preprocessing(sentinel2_mapchete):
    mp = sentinel2_mapchete.mp()
    input_data = list(mp.config.inputs.values())[0]
    assert input_data.products

    tile_mp = sentinel2_mapchete.process_mp()
    assert tile_mp.open("inp").products


def test_read_area_stac(sentinel2_stac_area_mapchete):
    with sentinel2_stac_area_mapchete.process_mp((13, 2003, 8906)).open("inp") as src:
        assert src.is_empty()
        with pytest.raises(NoSourceProducts):
            src.read(assets=["red"])


def test_read_area(sentinel2_area_mapchete):
    with sentinel2_area_mapchete.process_mp((13, 2003, 8906)).open("inp") as src:
        assert src.is_empty()
        with pytest.raises(NoSourceProducts):
            src.read(assets=["red"])


# InputData.read() #
####################


def test_read(sentinel2_stac_mapchete):
    with sentinel2_stac_mapchete.process_mp((13, 2003, 8906)).open("inp") as src:
        cube = src.read(assets=["red"])
    assert isinstance(cube, xr.Dataset)
    assert cube.to_array().any()
    assert cube.dims["s2:datastrip_id"] == 2


def test_read_masked(sentinel2_stac_mapchete):
    with sentinel2_stac_mapchete.process_mp((13, 1980, 8906)).open("inp") as src:
        unmasked = src.read(assets=["red"])
        masked = src.read(
            assets=["red"],
            mask_config=MaskConfig(
                footprint=True,
                scl=True,
                scl_classes=[
                    SceneClassification.vegetation,
                ],
            ),
        )
    datastrip = "S2B_OPER_MSI_L2A_DS_2BPS_20230813T130536_S20230813T100712_N05.09"
    assert masked[datastrip].any()
    assert (unmasked[datastrip] != masked[datastrip]).any()


def test_read_brdf(sentinel2_stac_mapchete):
    with sentinel2_stac_mapchete.process_mp((13, 2003, 8906)).open("inp") as src:
        uncorrected = src.read(assets=["red"])
        corrected = src.read(assets=["red"], brdf_config=BRDFConfig())
    for datastrip in corrected:
        assert corrected[datastrip].any()
        assert (uncorrected[datastrip] != corrected[datastrip]).any()


def test_read_empty_raise_nosourceproducts(sentinel2_stac_mapchete):
    # tile does not intersect with any products
    with sentinel2_stac_mapchete.process_mp((13, 0, 0)).open("inp") as src:
        with pytest.raises(NoSourceProducts):
            src.read(assets=["red"])


def test_read_empty_raise_emptystackexception(sentinel2_stac_mapchete):
    # tile intersects but products are empty
    with sentinel2_stac_mapchete.process_mp((13, 2003, 8906)).open("inp") as src:
        with pytest.raises(EmptyStackException):
            src.read(
                assets=["red"],
                mask_config=MaskConfig(
                    footprint=True,
                    l1c_clouds=True,
                    snow_ice=True,
                    cloud_probability=True,
                    cloud_probability_threshold=1,
                    scl=True,
                    scl_classes=list(SceneClassification),
                ),
            )


def test_read_empty(sentinel2_stac_mapchete):
    with sentinel2_stac_mapchete.process_mp((13, 2003, 8906)).open("inp") as src:
        stack = src.read(
            assets=["red"],
            mask_config=MaskConfig(
                footprint=True,
                l1c_clouds=True,
                snow_ice=True,
                cloud_probability=True,
                cloud_probability_threshold=1,
                scl=True,
                scl_classes=list(SceneClassification),
            ),
            raise_empty=False,
        )

    assert isinstance(stack, xr.Dataset)


def test_read_sorted(sentinel2_stac_mapchete):
    assets = ["red"]
    with sentinel2_stac_mapchete.process_mp((13, 2003, 8906)).open("inp") as src:
        cube_sorted = src.read(
            assets=assets, sort=TargetDateSort(target_date="2023-08-01")
        )
        cube_sorted_reverse = src.read(
            assets=assets, sort=TargetDateSort(target_date="2023-08-01", reverse=True)
        )
    assert [str(i) for i in cube_sorted] != [str(i) for i in cube_sorted_reverse]


# InputData.read_np_array() #
#############################


@pytest.mark.parametrize(
    "example_mapchete,tile",
    [
        (lazy_fixture("sentinel2_stac_mapchete"), (13, 2003, 8906)),
        (lazy_fixture("sentinel2_antimeridian_east_mapchete"), (13, 1039, 16379)),
        (lazy_fixture("sentinel2_antimeridian_west_mapchete"), (13, 1039, 1)),
    ],
)
def test_read_np(example_mapchete, tile):
    with example_mapchete.process_mp(tile).open("inp") as src:
        cube = src.read_np_array(assets=["red"])
    assert isinstance(cube, ma.MaskedArray)
    assert cube.any()
    assert cube.shape[0] == 2


@pytest.mark.parametrize(
    "example_mapchete,tile",
    [
        (lazy_fixture("sentinel2_stac_mapchete"), (13, 2003, 8906)),
        (lazy_fixture("sentinel2_antimeridian_east_mapchete"), (13, 1039, 16379)),
        (lazy_fixture("sentinel2_antimeridian_west_mapchete"), (13, 1024, 28)),
    ],
)
def test_read_np_masked(example_mapchete, tile):
    with example_mapchete.process_mp(tile).open("inp") as src:
        unmasked = src.read_np_array(assets=["red"])
        masked = src.read_np_array(
            assets=["red"],
            mask_config=MaskConfig(
                footprint=True,
                scl=True,
                scl_classes=[
                    SceneClassification.vegetation,
                ],
            ),
        )
    assert masked.any()
    assert (unmasked.mask != masked.mask).any()


@pytest.mark.parametrize(
    "example_mapchete,tile",
    [
        (lazy_fixture("sentinel2_stac_mapchete"), (13, 2003, 8906)),
        (lazy_fixture("sentinel2_antimeridian_east_mapchete"), (13, 1039, 16379)),
        (lazy_fixture("sentinel2_antimeridian_west_mapchete"), (13, 1039, 1)),
    ],
)
def test_read_np_brdf(example_mapchete, tile):
    with example_mapchete.process_mp(tile).open("inp") as src:
        uncorrected = src.read_np_array(assets=["red"])
        corrected = src.read_np_array(assets=["red"], brdf_config=BRDFConfig())
    assert corrected.any()
    assert (uncorrected != corrected).any()


def test_read_np_empty_raise_nosourceproducts(sentinel2_stac_mapchete):
    # tile does not intersect with any products
    with sentinel2_stac_mapchete.process_mp((13, 0, 0)).open("inp") as src:
        with pytest.raises(NoSourceProducts):
            src.read_np_array(assets=["red"])


def test_read_np_empty_raise_emptystackexception(sentinel2_stac_mapchete):
    with sentinel2_stac_mapchete.process_mp((13, 1980, 8906)).open("inp") as src:
        with pytest.raises(EmptyStackException):
            src.read_np_array(
                assets=["red"],
                mask_config=MaskConfig(
                    footprint=True,
                    l1c_clouds=True,
                    snow_ice=True,
                    cloud_probability=True,
                    cloud_probability_threshold=1,
                    scl=True,
                    scl_classes=list(SceneClassification),
                ),
            )


def test_read_np_empty(sentinel2_stac_mapchete):
    with sentinel2_stac_mapchete.process_mp((13, 1980, 8906)).open("inp") as src:
        stack = src.read_np_array(
            assets=["red"],
            mask_config=MaskConfig(
                footprint=True,
                l1c_clouds=True,
                snow_ice=True,
                cloud_probability=True,
                cloud_probability_threshold=1,
                scl=True,
                scl_classes=list(SceneClassification),
            ),
            raise_empty=False,
        )
    assert isinstance(stack, ma.MaskedArray)
    assert not stack.any()
    assert stack.shape[0] == 2


# InputData.read_levelled() #
#############################


def test_read_levelled_cube_xarray(sentinel2_stac_mapchete, test_tile):
    with sentinel2_stac_mapchete.process_mp(test_tile).open("inp") as src:
        assets = ["red"]
        target_height = 5
        xarr = src.read_levelled(
            target_height=target_height,
            assets=assets,
            mask_config=MaskConfig(
                l1c_clouds=True,
                cloud_probability=True,
                cloud_probability_threshold=50,
            ),
        )
    assert isinstance(xarr, xr.Dataset)

    arr = to_masked_array(xarr)
    assert arr.any()
    assert not arr.mask.all()
    assert arr.shape[0] == target_height

    # not much a better way of testing it than to make sure, cube is filled from the bottom
    layers = list(range(target_height))
    for lower, higher in zip(layers[:-1], layers[1:]):
        assert arr[lower].mask.sum() <= arr[higher].mask.sum()


# InputData.read_levelled_np_array() #
######################################


def test_read_levelled_cube_np_array(sentinel2_stac_mapchete, test_tile):
    with sentinel2_stac_mapchete.process_mp(test_tile).open("inp") as src:
        assets = ["red"]
        target_height = 5
        arr = src.read_levelled_np_array(
            target_height=target_height,
            assets=assets,
            mask_config=MaskConfig(
                l1c_clouds=True,
                cloud_probability=True,
                cloud_probability_threshold=50,
            ),
        )
    assert isinstance(arr, ma.MaskedArray)
    assert arr.any()
    assert not arr.mask.all()
    assert arr.shape[0] == target_height

    # not much a better way of testing it than to make sure, cube is filled from the bottom
    layers = list(range(target_height))
    for lower, higher in zip(layers[:-1], layers[1:]):
        assert arr[lower].mask.sum() <= arr[higher].mask.sum()


def test_read_levelled_cube_np_array_sort(sentinel2_stac_mapchete, test_tile):
    with sentinel2_stac_mapchete.process_mp(test_tile).open("inp") as src:
        assets = ["red"]
        target_height = 1
        arr = src.read_levelled_np_array(
            target_height=target_height,
            assets=assets,
            sort=TargetDateSort(target_date="2023-08-01", reverse=False),
        )
        arr_reversed = src.read_levelled_np_array(
            target_height=target_height,
            assets=assets,
            sort=TargetDateSort(target_date="2023-08-01", reverse=True),
        )
        assert ma.not_equal(arr, arr_reversed).any()


@pytest.mark.parametrize(
    "mask_config",
    [
        # L1C cloud type as string
        dict(l1c_cloud_type="cirrus"),
        dict(l1c_cloud_type="opaque"),
        dict(l1c_cloud_type="all"),
        # SCL class as string
        dict(scl_classes=["vegetation"]),
        # QI band resolution as string
        dict(cloud_probability_resolution=20),
        # snow/ice
        dict(snow_ice=True),
    ],
)
def test_parse_mask_config(mask_config):
    assert MaskConfig.parse(mask_config)


def test_footprint_buffer(sentinel2_stac_mapchete, test_edge_tile):
    # read data from both processes and make sure footprint buffered data is masked out more

    with sentinel2_stac_mapchete.process_mp(test_edge_tile).open("inp") as src:
        unbuffered = src.read_np_array(
            assets=["red"],
            mask_config=MaskConfig(footprint=True, footprint_buffer_m=0),
        )

    with sentinel2_stac_mapchete.process_mp(test_edge_tile).open("inp") as src:
        buffered = src.read_np_array(
            assets=["red"],
            mask_config=MaskConfig(footprint=True, footprint_buffer_m=-500),
        )

    assert buffered.mask.sum() > unbuffered.mask.sum()


# def test_footprint_buffer_antimeridian(
#     sentinel2_stac_mapchete, sentinel2_stac_footprint_buffer_mapchete, test_edge_tile
# ):
#     # read data from both processes and make sure footprint buffered data is masked out more

#     with sentinel2_stac_mapchete.process_mp(test_edge_tile).open("inp") as src:
#         unbuffered = src.read_np_array(
#             assets=["red"],
#             mask_config=MaskConfig(
#                 footprint=True,
#             ),
#         )

#     with sentinel2_stac_footprint_buffer_mapchete.process_mp(test_edge_tile).open(
#         "inp"
#     ) as src:
#         buffered = src.read_np_array(
#             assets=["red"],
#             mask_config=MaskConfig(
#                 footprint=True,
#             ),
#         )

#     assert buffered.mask.sum() > unbuffered.mask.sum()
