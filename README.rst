.. image:: logo/mapchete_eo.svg

Earth Observation–specific driver extensions for `Mapchete <https://github.com/ungarj/mapchete>`_.

.. image:: https://img.shields.io/pypi/v/mapchete-eo.svg
  :target: https://pypi.org/project/mapchete-eo/

.. image:: https://img.shields.io/conda/v/conda-forge/mapchete-eo
  :target: https://anaconda.org/conda-forge/mapchete-eo

.. image:: https://img.shields.io/pypi/l/mapchete-eo.svg
  :target: https://github.com/mapchete/mapchete-eo/blob/main/LICENSE

.. image:: https://img.shields.io/github/actions/workflow/status/mapchete/mapchete-eo/python-package.yml?label=tests
  :target: https://github.com/mapchete/mapchete-eo/actions

.. image:: https://codecov.io/gh/mapchete/mapchete-eo/graph/badge.svg?token=VD1YOF3QA2
  :target: https://codecov.io/gh/mapchete/mapchete-eo

.. image:: https://img.shields.io/github/repo-size/mapchete/mapchete-eo
  :target: https://github.com/mapchete/mapchete-eo

This package provides custom input and output drivers tailored for common EO data formats and workflows, enabling seamless integration of satellite data sources into the Mapchete tile-based geoprocessing framework.

What is this?
-------------

**mapchete-eo** extends Mapchete by adding support for:

- Custom **input drivers** to read EO datasets, from STAC search or metadata (catalogs, collections, items)
- Metadata extraction and band management for optical satellite products
- Reading data from sources via **STAC assets**

This package is intended for advanced users or developers who are working with remote sensing workflows using Mapchete.

Installation
------------

You must have ``mapchete`` with ``s3`` installed, so let's grab the ``complete`` dependencies in this case for convenience:

.. code-block:: bash

    pip install mapchete[complete]

Then install mapchete-eo:

.. code-block:: bash

    pip install mapchete-eo
