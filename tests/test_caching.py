
from mapchete.path import MPath

from mapchete_eo.caching import cache_file


def test_cache_file(
        test_array,
        test_affine,
        test_cache_path
):
    out_file_path = MPath(
        cache_file(
            in_array=test_array,
            in_affine=test_affine,
            in_array_dtype="uint8",
            nodata=0,
            epsg=3857,
            out_file_path=test_cache_path,
            out_file_suffix='tif'
        )
    )
    assert out_file_path.exists()
    out_file_path.rm()
