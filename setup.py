"""Setup script for mapchete plugin."""
from itertools import chain

from setuptools import find_namespace_packages, setup

# get version number
# from https://github.com/mapbox/rasterio/blob/master/setup.py#L55
with open("src/mapchete_eo/__init__.py") as f:
    for line in f:
        if line.find("__version__") >= 0:
            version = line.split("=")[1].strip()
            version = version.strip('"')
            version = version.strip("'")
            break

# use README for project long_description
with open("README.md") as f:
    readme = f.read()

# package requirements
install_requires = [
    "mapchete>=2022.2.2",
    "pydantic",
    "pystac",
    "pystac_client",
    "rtree",
    "xarray",
]
extras_require = {}
extras_require.update(complete=set(chain(*[v for v in extras_require.values()])))

setup(
    name="mapchete_eo",
    version=version,
    description="Mapchete EO data reader",
    long_description=readme,
    author="Joachim Ungar",
    author_email="joachim.ungar@eox.at",
    url="https://gitlab.eox.at/maps/mapchete_eo",
    license="MIT",
    packages=find_namespace_packages(where="src"),
    package_dir={"": "src"},
    package_data={},
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "mapchete.cli.commands": [
            "eo=mapchete_eo.cli.main:eo",
        ],
        "mapchete.formats.drivers": [
            "eostac=mapchete_eo.eostac",
            "sentinel2=mapchete_eo.sentinel2",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: GIS",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)
