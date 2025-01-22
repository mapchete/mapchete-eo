import numpy.ma as ma

from mapchete_eo.processes import (
    dtype_scale,
    merge_rasters,
)


def test_eoxcloudless_8bit_dtype_scale_mapchete(eoxcloudless_8bit_dtype_scale_mapchete):
    process_mp = eoxcloudless_8bit_dtype_scale_mapchete.process_mp()
    output = dtype_scale.execute(process_mp, process_mp.open("inp"))
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.any()
    assert ma.mean(output) < 100


def test_merge_rasters(merge_rasters_mapchete):
    process_mp = merge_rasters_mapchete.process_mp()
    # calling the execute() function directly from the process module means
    # we have to provide all kwargs usually found in the process_parameters
    output = merge_rasters.execute(
        process_mp,
        process_mp.open("rasters"),
        process_mp.open("vectors"),
        **process_mp.params.get("process_parameters", {}),
    )
    assert isinstance(output, ma.MaskedArray)
    assert not output.mask.all()
    assert ma.mean(output) > 200
