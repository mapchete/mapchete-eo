Examples
==========================================

Examples can be found in the `examples` directory of this repository.

List of available examples:

1) `sentinel-2_2025-may-june_first-pixel.mapchete`
2) *placeholder*

Usage
-----

Here is how to execute the `mapchete-eo` drivers via `mapchete execute` on one of the examples.

.. code-block:: bash

 $ mapchete execute sentinel-2_2025-may-june_first-pixel.mapchete

This will run `mapchete executor` (default: processes) and output the processing into the `path` under `output` specified in the mapchete file config.

The `sentinel-2_2025-may-june_first-pixel.mapchete` example shows capabilities by reading the Element84 curated Sentinel-2 Cloud-Optimized GeoTiff (COG) data, which can be read publicly without incurring costs.

For data discovery we are using the STAC API EarthSearch (https://earth-search.aws.element84.com/v1).