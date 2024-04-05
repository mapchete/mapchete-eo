import pytest
from click.testing import CliRunner
from mapchete.io import rasterio_open
from pytest_lazyfixture import lazy_fixture

from mapchete_eo.cli import eo
from mapchete_eo.known_catalogs import EarthSearchV1S2L2A


def test_s2_mask(s2_stac_json_half_footprint, tmp_mpath):
    runner = CliRunner()
    out_path = tmp_mpath / "mask.tif"
    result = runner.invoke(
        eo,
        [
            "s2-mask",
            str(s2_stac_json_half_footprint),
            "--resolution",
            "120m",
            "--mask-footprint",
            str(out_path),
        ],
    )
    assert result.exit_code == 0
    assert out_path.exists()
    with rasterio_open(out_path) as src:
        assert src.read().any()


def test_s2_rgb(s2_stac_json_half_footprint, tmp_mpath):
    runner = CliRunner()
    out_path = tmp_mpath / "rgb.tif"
    result = runner.invoke(
        eo,
        [
            "s2-rgb",
            str(s2_stac_json_half_footprint),
            "--resolution",
            "120m",
            "--dst-path",
            str(out_path),
        ],
    )
    assert result.exit_code == 0
    assert out_path.exists()
    with rasterio_open(out_path) as src:
        assert not src.read(masked=True).mask.all()


def test_s2_brdf(s2_stac_json_half_footprint, tmp_mpath):
    runner = CliRunner()
    out_path = tmp_mpath
    result = runner.invoke(
        eo,
        [
            "s2-brdf",
            str(s2_stac_json_half_footprint),
            "--resolution",
            "120m",
            "--dump-detector-footprints",
            "--l2a-bands",
            "B02",
            str(out_path),
        ],
    )
    assert result.exit_code == 0
    assert len(out_path.ls()) == 2
    for path in out_path.ls():
        with rasterio_open(path) as src:
            assert not src.read(masked=True).mask.all()


@pytest.mark.remote
@pytest.mark.parametrize(
    "flag,value,collection",
    [
        ("--catalog-json", lazy_fixture("s2_stac_collection"), None),
        ("--archive", "S2AWS_COG", None),
        ("--endpoint", EarthSearchV1S2L2A.endpoint, "sentinel-2-l2a"),
    ],
)
def test_static_catalog(tmp_mpath, flag, value, collection):
    runner = CliRunner()
    out_path = tmp_mpath
    params = [
        "static-catalog",
        "--bounds",
        "16",
        "46",
        "16.0001",
        "46.0001",
        "--start-time",
        "2023-08-10",
        "--end-time",
        "2023-08-10",
        flag,
        value,
        str(out_path),
    ]
    if collection:
        params.extend(["--collection", collection])
    result = runner.invoke(eo, params)
    assert result.exit_code == 0
    assert out_path.ls()
