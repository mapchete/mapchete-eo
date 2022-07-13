Configuration Parameters
========================

All configuration parameters can be either set in the mapchete file or via environment
variables as long as the variables are provided in uppercase letters and have the
:code:`MP_SATELLITE_` prefix.

Some parameters also come with default values. Please note that the values coming from
environment variables overrule mapchete file values which themselves overrule default
values.


-----------------
Common Parameters
-----------------

:code:`start_time` / :code:`end_time`
---------------------------------------
*(required)*

Start and end time filter settings for input products.

:code:`remote_timeout`
----------------------
*(default: 5)*

Timeout in seconds used for all packages which make calls to external services. These
packages are :code:`urllib`, :code:`requests`, :code:`rasterio`, :code:`fiona` and
:code:`boto`.

:code:`metadata_concurrency`
----------------------------
*(default: True)*

Parse and prepare metadata in parallel.

:code:`metadata_concurrency_parallelization`
--------------------------------------------
*(one of "threads" or "processes"; default: "threads")*

Parallelization strategy.

:code:`metadata_concurrency_threads`
------------------------------------
*(default: number of CPU cores but 8 at maximum)*

Number of parallel threads used.

:code:`metadata_concurrency_processes`
--------------------------------------
*(default: number of CPU cores but 8 at maximum)*

Number of parallel processes used.

:code:`footprint_buffer`
------------------------
*(default: -500)*

Buffer used to make footprints a bit smaller. The reason is that product bands do not
exactly overlap at the edges and therefore can cause artefacts ("unicorn trails").

:code:`max_products`
--------------------
*(default: 4500)*

Maximum number of products allowed to be parsed before plugin raises an error.

:code:`max_cloud_percent`
-------------------------
*(default: 100)*

Filter setting for maximum cloud coverage.

:code:`first_granule_only`
--------------------------
*(default: False)*

Only use the first product of the day, e.g. in higher latitudes where multiple products
overlap in one day, the plugin only uses the first product and omits the rest. This avoids
reading unnecessary amounts of data in regions which are covered multiple times by day.


Common Caching Parameters
-------------------------

:code:`path`
------------
*(required)*

Local path to cache products.


:code:`intersection_percent`
----------------------------
*(default: 100)*

Only cache products which intersect to x percent with process bounds.

:code:`keep`
------------
*(default: False)*

Don't clean cache after process is finished. This setting makes debugging easier.

:code:`max_disk_usage`
------------------------------------
*(default: 90)*

Stop caching products if disk is more thatn x % full.


-------------------
Sentinel-1 Specific
-------------------

:code:`level`
-------------
*(currently only "L1" supported; default: "L1")*

Filter setting for processing level.

:code:`sensormode`
------------------
*(currently only "IW" supported; default: "IW")*

Filter setting for sensor mode.

:code:`producttype`
-------------------
*(one of "GRD", "IW_SLC" or "EW_SLC"; default: "GRD")*

Filter setting for product type.


Specific Caching Parameters
---------------------------

Note: caching is required for Sentinel-1!

:code:`resampling`
------------------
*(default: nearest)*

Resampling method used when projecting raw data.

:code:`sar_calibration`
-----------------------
*(one of "Beta", "Gamma" or "Sigma"; default: "Gamma")*

SNAP calibration method used when preprocessing data.

:code:`tnr`
-----------
*(default: True)*

SNAP TNR magic.

:code:`zoom`
------------
*(default: 13)*

Process pyramid zoom level to determine projection target grid.


-------------------
Sentinel-2 Specific
-------------------

:code:`level`
-------------
*(one of "L1C" or "L2A"; default: "L1")*

Filter setting for processing level. Note: "L2A" is currently only available on Mundi.


Specific Caching Parameters
---------------------------

:code:`scl`
-----------
*(default: False)*

Also cache SCL data. (Only relevant when using Level-2.)


------------
AWS Specific
------------

:code:`cat_baseurl`
-------------------
*(default: "http://opensearch.sentinel-hub.com/resto/api/collections/Sentinel2/search.json?q=&")*

URL to opensearch catalog.

:code:`bucket_baseurl`
----------------------
*(default: "s3://sentinel-s2-l1c/")*

Base URL to bucket containing the data.

:code:`metadata_baseurl`
------------------------
*(default: "s3://sentinel-s2-l1c/")*

Base URL to bucket containing metadata.


-------------------------
Sentinel-1 Mundi Specific
-------------------------

:code:`cat_baseurl`
-------------------
*(default: "https://mundiwebservices.com/acdc/catalog/proxy/search/Sentinel1/opensearch?&")*

URL to opensearch catalog.

:code:`bucket_baseurl`
----------------------
*(default: "https://obs.eu-de.otc.t-systems.com/")*

Base URL to bucket containing the data.


-------------------------
Sentinel-2 Mundi Specific
-------------------------

:code:`cat_baseurl`
-------------------
*(default: "https://mundiwebservices.com/acdc/catalog/proxy/search/Sentinel2/opensearch?&")*

URL to opensearch catalog.

:code:`bucket_baseurl`
----------------------
*(default: "https://obs.eu-de.otc.t-systems.com/")*

Base URL to bucket containing the data.
