from mapchete import MapcheteNodataTile
import numpy.ma as ma
import pytest

from mapchete_eo.image_operations import FillSelectionMethod
from mapchete_eo.processes import (
    dtype_scale,
    eoxcloudless_mosaic,
    eoxcloudless_mosaic_merge,
    eoxcloudless_rgb_map,
    eoxcloudless_sentinel2_color_correction,
    eoxcloudless_scl_mosaic,
    merge_rasters,
)


def test_eoxcloudless_8bit_dtype_scale_mapchete(eoxcloudless_8bit_dtype_scale_mapchete):
    process_mp = eoxcloudless_8bit_dtype_scale_mapchete.process_mp()
    output = dtype_scale.execute(process_mp, process_mp.open("inp"))
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.mean(output) < 100


@pytest.mark.parametrize("fillnodata", [True, False])
@pytest.mark.parametrize("fillnodata_method", [FillSelectionMethod.all, "all"])
@pytest.mark.parametrize("desert_color_correction_flag", [True, False])
def test_eoxcloudless_sentinel2_color_correction(
    eoxcloudless_sentinel2_color_correction_mapchete,
    fillnodata,
    fillnodata_method,
    desert_color_correction_flag,
):
    process_mp = eoxcloudless_sentinel2_color_correction_mapchete.process_mp()
    output = eoxcloudless_sentinel2_color_correction.execute(
        process_mp.open("mosaic"),
        desert_mask=process_mp.open("desert_mask"),
        fillnodata=fillnodata,
        fillnodata_method=fillnodata_method,
        desert_color_correction_flag=desert_color_correction_flag,
    )
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.mean(output) < 200


def test_eoxcloudless_rgb_map(eoxcloudless_rgb_map_mapchete):
    process_mp = eoxcloudless_rgb_map_mapchete.process_mp()
    output = eoxcloudless_rgb_map.execute(
        process_mp.open("mosaic"),
        process_mp.open("mosaic_mask"),
        process_mp.open("land_mask"),
        process_mp.open("fuzzy_ocean_mask"),
        process_mp.open("ocean_depth"),
        process_mp.open("bathymetry"),
    )
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.mean(output) < 200


def test_eoxcloudless_rgb_map_mosaic_mask(eoxcloudless_rgb_map_mapchete):
    process_mp = eoxcloudless_rgb_map_mapchete.process_mp(tile=(6, 56, 103))
    output = eoxcloudless_rgb_map.execute(
        process_mp.open("mosaic"),
        process_mp.open("mosaic_mask"),
        process_mp.open("land_mask"),
        process_mp.open("fuzzy_ocean_mask"),
        process_mp.open("ocean_depth"),
        process_mp.open("bathymetry"),
    )
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.min(output) == 255
    assert ma.mean(output) == 255
    assert ma.max(output) == 255


@pytest.mark.remote
def test_eoxcloudless_mosaic(eoxcloudless_mosaic_mapchete):
    process_mp = eoxcloudless_mosaic_mapchete.process_mp()
    # calling the execute() function directly from the process module means
    # we have to provide all kwargs usually found in the process_parameters
    output = eoxcloudless_mosaic.execute(
        process_mp.open("sentinel2"),
        assets=["red", "green", "blue", "nir"],
        mask_config=dict(scl_classes=["vegetation"]),
    )
    assert isinstance(output, ma.MaskedArray)
    assert output.mask.any()
    assert ma.mean(output) > 200


@pytest.mark.skip(
    reason="area parameter in raster_file driver has to be implemented by mapchete first"
)
def test_merge_rasters(merge_rasters_mapchete):
    process_mp = merge_rasters_mapchete.process_mp()
    # calling the execute() function directly from the process module means
    # we have to provide all kwargs usually found in the process_parameters
    output = merge_rasters.execute(
        process_mp, **process_mp.params.get("process_parameters", {})
    )
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.all()
    assert ma.mean(output) > 200


def test_eoxcloudless_mosaic_regions_merge(eoxcloudless_mosaic_regions_merge_mapchete):
    process_mp = eoxcloudless_mosaic_regions_merge_mapchete.process_mp()
    # calling the execute() function directly from the process module means
    # we have to provide all kwargs usually found in the process_parameters
    output = eoxcloudless_mosaic_merge.execute(
        process_mp.open("sentinel2"),
        process_mp,
        **process_mp.params.get("process_parameters", {}),
    )
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.all()
    assert ma.mean(output) > 200


@pytest.mark.parametrize(
    "selection_method",
    [
        eoxcloudless_scl_mosaic.SelectionMethod.first_permanent,
        eoxcloudless_scl_mosaic.SelectionMethod.majority,
    ],
)
def test_eoxcloudless_scl_mosaic(eoxcloudless_mosaic_mapchete, selection_method):
    sentinel2_input_tile = eoxcloudless_mosaic_mapchete.process_mp().open("sentinel2")
    eoxcloudless_scl_mosaic.execute(
        sentinel2_input_tile, selection_method=selection_method
    )


def test_eoxcloudless_scl_mosaic_empty(eoxcloudless_mosaic_mapchete):
    sentinel2_input_tile = eoxcloudless_mosaic_mapchete.process_mp(tile=(9, 0, 0)).open(
        "sentinel2"
    )
    with pytest.raises(MapcheteNodataTile):
        eoxcloudless_scl_mosaic.execute(sentinel2_input_tile)
