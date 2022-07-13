import os

import pytest
from mapchete.io import fs_from_path
from mapchete.testing import ProcessFixture

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TESTDATA_DIR = os.path.join(SCRIPT_DIR, "testdata")


@pytest.fixture
def stac_mapchete(tmp_path):
    with ProcessFixture(
        os.path.join(TESTDATA_DIR, "stac.mapchete"),
        output_tempdir=tmp_path,
    ) as example:
        yield example
