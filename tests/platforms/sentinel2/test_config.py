import pytest

from mapchete_eo.platforms.sentinel2.config import Sentinel2DriverConfig


@pytest.mark.parametrize(
    "config_dict",
    [
        dict(),
        dict(
            source="EarthSearch",
        ),
        dict(
            source=["EarthSearch"],
        ),
        dict(
            source=[
                dict(
                    stac_catalog="EarthSearch",
                    metadata_archive="roda",
                )
            ],
        ),
        dict(
            source=[
                dict(
                    stac_catalog="EarthSearch",
                ),
                dict(stac_catalog="CDSE", data_archive="AWSJP2"),
            ],
        ),
        dict(
            source=[
                dict(
                    stac_catalog="https://earth-search.aws.element84.com/v1/",
                    collections=["sentinel-s2-l2a"],
                ),
            ],
        ),
    ],
)
def test_valid_configs(config_dict: dict):
    config = Sentinel2DriverConfig.model_validate(
        dict(
            config_dict,
            format="Sentinel-2",
            time=dict(start="2025-10-01", end="2025-10-01"),
        )
    )
    assert config.source
    for source in config.source:
        assert source.stac_catalog
        assert source.collections
