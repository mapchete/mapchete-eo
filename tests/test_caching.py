import pytest
from mapchete.io import rasterio_open
from mapchete.path import MPath

from mapchete_eo.io import cache_to_file


def test_cache_raster_file_to_dir(test_array, test_affine, tmp_path):
    out_dir = MPath(str(tmp_path))
    out_file = cache_to_file(
        in_array=test_array,
        in_affine=test_affine,
        in_array_dtype="uint8",
        nodata=0,
        crs=3857,
        out_file_path=out_dir,
        out_file_suffix="tif",
    )
    assert out_file.exists()
    with rasterio_open(out_file) as src:
        assert not src.read(masked=True).mask.all()


def test_cache_raster_file_to_file(test_array, test_affine, tmp_path):
    out_dir = MPath(str(tmp_path)) / "temp.tif"
    out_file = cache_to_file(
        in_array=test_array,
        in_affine=test_affine,
        in_array_dtype="uint8",
        nodata=0,
        crs=3857,
        out_file_path=out_dir,
        out_file_suffix="tif",
    )
    assert out_file.exists()
    with rasterio_open(out_file) as src:
        assert not src.read(masked=True).mask.all()
