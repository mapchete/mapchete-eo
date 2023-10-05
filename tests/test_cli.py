import pytest
from click.testing import CliRunner
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
            str(out_path),
        ],
    )
    assert result.exit_code == 0
    assert out_path.exists()


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
            str(out_path),
        ],
    )
    assert result.exit_code == 0
    assert out_path.exists()


@pytest.mark.remote
@pytest.mark.parametrize(
    "flag,value,collection",
    [
        ("--catalog-json", lazy_fixture("s2_stac_collection"), None),
        ("--archive", "sentinel-s2-l2a-cogs", None),
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
