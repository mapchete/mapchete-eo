Usage Guide
===========

Introduction
------------

**mapchete-eo** extends Mapchete with Earth Observation specific capabilities. This guide covers common patterns for data discovery and processing.

Data Discovery (Search)
-----------------------

Search for data using `Source` objects.

.. code-block:: python

    from mapchete_eo.source import Source

    source = Source(
        collection="sentinel-2-l2a",
        catalog_type="stac",
        # ... other config
    )

    # Search for items
    items = list(source.search(area=roi, time="2023-01-01/2023-01-31"))

Reading Data
------------

Products are used to read data into `xarray` or `numpy` cubes.

.. code-block:: python

    # Inside a mapchete process
    def execute(mp, **kwargs):
        with mp.open("sentinel-2") as s2:
            # Read as xarray
            ds = s2.read(eo_bands=["red", "green", "blue"])
            
            # Read as MaskedArray
            arr = s2.read_np_array(eo_bands=["nir"])

Compositing and Blending
------------------------

You can use various blending methods to combine overlapping products.

.. code-block:: python

    from mapchete_eo.image_operations.compositing import composite

    # Composite foreground and background using 'multiply'
    blended = composite("multiply", bg_arr, fg_arr)

Example Workflow
----------------

1. Define your tileset and process area in a `.mapchete` file.
2. Use `mapchete-eo` drivers (e.g., `sentinel2`) to declare inputs.
3. Access and process Earth Observation data with high-level API functions.
