Examples
==========================================

Examples can be found in the `examples` directory of this repository.

List of available Examples
========

Mapchete-EO Drivers
-------------------

You can execute mapchete-eo drivers as any other mapchete processes.


Sentinel-2 First Pixel
-----------------------

This example uses Sentinel-2 data and picks the first available cloud-free pixel from a time range.

* `Config <https://github.com/mapchete/mapchete-eo/blob/main/examples/sentinel-2_2025-may-june_first_pixel.mapchete>`_
* `Process <https://github.com/mapchete/mapchete-eo/blob/main/examples/first_pixel_process.py>`_


Sentinel-2 NDVI
---------------

Calculate the Normalized Difference Vegetation Index (NDVI) from Sentinel-2 data.

* `Config <https://github.com/mapchete/mapchete-eo/blob/main/examples/ndvi.mapchete>`_
* `Process <https://github.com/mapchete/mapchete-eo/blob/main/examples/ndvi_process.py>`_


Sentinel-2 Temporal Mean
------------------------

Create a temporal mean composite of cloud-free pixels over a given time range.

* `Config <https://github.com/mapchete/mapchete-eo/blob/main/examples/temporal_mean.mapchete>`_
* `Process <https://github.com/mapchete/mapchete-eo/blob/main/examples/temporal_mean_process.py>`_

Usage
-----

Here is how to execute the `mapchete-eo` drivers via `mapchete execute` on one of the examples.

.. code-block:: bash

 $ mapchete execute sentinel-2_2025-may-june_first-pixel.mapchete

This will run `mapchete executor` (default: processes) and output the processing into the `path` under `output` specified in the mapchete file config.

The `sentinel-2_2025-may-june_first-pixel.mapchete` example shows capabilities by reading the Element84 curated Sentinel-2 Cloud-Optimized GeoTiff (COG) data, which can be read publicly without incurring costs.

For data discovery we are using the STAC API EarthSearch (https://earth-search.aws.element84.com/v1).