import numpy.ma as ma
import pytest
import xarray as xr
from mapchete.formats import available_input_formats

from mapchete_eo.exceptions import EmptyStackException, NoSourceProducts
from mapchete_eo.platforms.sentinel2.config import (
    BRDFConfig,
    MaskConfig,
    SceneClassification,
    Sentinel2DriverConfig,
)


def test_format_available():
    assert "Sentinel-2" in available_input_formats()


def test_config():
    conf = Sentinel2DriverConfig(
        format="Sentinel-2",
        start_time="2022-04-01",
        end_time="2022-04-10",
    )
    assert conf.dict()


@pytest.mark.remote
def test_remote_s2_read_xarray(sentinel2_mapchete):
    with sentinel2_mapchete.process_mp().open("inp") as cube:
        assert isinstance(cube.read(assets=["coastal"]), xr.Dataset)


def test_preprocessing(sentinel2_mapchete):
    mp = sentinel2_mapchete.mp()
    input_data = list(mp.config.inputs.values())[0]
    assert input_data.products

    tile_mp = sentinel2_mapchete.process_mp()
    assert tile_mp.open("inp").products


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
                    cloud=True,
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
                cloud=True,
                snow_ice=True,
                cloud_probability=True,
                cloud_probability_threshold=1,
                scl=True,
                scl_classes=list(SceneClassification),
            ),
            raise_empty=False,
        )

    assert isinstance(stack, xr.Dataset)


def test_read_np(sentinel2_stac_mapchete):
    with sentinel2_stac_mapchete.process_mp((13, 2003, 8906)).open("inp") as src:
        cube = src.read_np_array(assets=["red"])
    assert isinstance(cube, ma.MaskedArray)
    assert cube.any()
    assert cube.shape[0] == 2


def test_read_np_masked(sentinel2_stac_mapchete):
    with sentinel2_stac_mapchete.process_mp((13, 1980, 8906)).open("inp") as src:
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


def test_read_np_brdf(sentinel2_stac_mapchete):
    with sentinel2_stac_mapchete.process_mp((13, 2003, 8906)).open("inp") as src:
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
                    cloud=True,
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
                cloud=True,
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


# def test_read_levelled(sentinel2_stac_mapchete):
#     s2_src = sentinel2_stac_mapchete.process_mp().open("inp")
#     cube = s2_src.read_levelled(["red", "green", "blue", "nir"], 2)
#     assert isinstance(cube, xr.Dataset)


# def test_read_ma(sentinel2_stac_mapchete):
#     s2_src = sentinel2_stac_mapchete.process_mp().open("inp")
#     cube = s2_src.read_ma(assets=["red", "green", "blue", "nir"])
#     assert isinstance(cube, ma.MaskedArray)


# def test_read_levelled_ma(sentinel2_stac_mapchete):
#     s2_src = sentinel2_stac_mapchete.process_mp().open("inp")
#     cube = s2_src.read_levelled_ma(["red", "green", "blue", "nir"])
#     assert cube.ndims == 4
#     assert isinstance(cube, ma.MaskedArray)
