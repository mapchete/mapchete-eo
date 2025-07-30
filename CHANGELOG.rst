#########
Changelog
#########


2025.7.0 - 2025-07-30
----------------------

* Migrated public repository at: `https://github.com/mapchete/mapchete-eo`
* Package name changed from `mapchete_eo` to `mapchete-eo`; python module still with underscore `from mapchete_eo import *`

* core
  
  * added/implemented `CDSESearch(STACSearchCatalog)` as search
  * added following archive options to utilize the CDSE seach, the `S2CDSE_AWSJP2` searches at CDSE, but reads from `AWS Open Data Sentinel-2`, 
    `S2CDSE_JP2` searches and reads data both from CDSE (needs to have correct asset names given for reading):

    * `S2CDSE_AWSJP2 = AWSL2AJP2CSDE`
    * `S2CDSE_JP2 = CDSEL2AJP2CSDE`

* CI/CD

  * `.github/workflows/` for running tests and publishing the `mapchete-eo` releases via hatch to `pypi`
  * removed double dependency files, now dependencies are defined in `pyproject.toml`


2025.5.0 - 2025-05-19
----------------------

* core

  * set `clip_to_crs_bounds=False` in `reproject_geometry` of `platforms.sentinel2.product` `footprint_nodata_mask()` as if clipped and at CRS border it will for some reason clip products; this make footprints too large or missprojected
    * This can also be due to smaller CRS bounds (from `pyproj`) than mapchete Grid Pyramid definition
  * use `|` in `platforms.sentinel2.product` `get_mask()` function to preserve `bool` types while going through masks
  * fix `first` Slice product reading logic, also make `average` for read_products and `all` for `read_masks` to only use products that are not fully masked

* CI/CD

  * use `registry.gitlab.eox.at/maps/docker-base/mapchete:2025.5.0` image for testing


2025.4.0 - 2025-04-17
----------------------

* CLI

  * add `cat-results` for Sentinel-2 Products and Slices (Datastripes), with indexes (start at 1)
  * Use MultiPolygons in case Slices are broken/split, due to data incoherence or antimeridian

* core

  * fix `max_cloud_cover` for searches, add more tests to cover usage
  * read masks as slices in `mapchete_eo.platforms.sentinel2.masks` with some tests
  * add `get_mask()` methods to `EOProduct` and its protocol as dummy to inherit properly down to `S2Product`
  * fix/clip negative values to 1 after scaling for Sentinel-2 value offset, while reading assets, it was creating false nodata and we decided to keep dtype `uint16`

* CI/CD

  * use `registry.gitlab.eox.at/maps/docker-base/mapchete:2025.4.0` image for testing


2025.1.2 - 2025-01-24
----------------------

* core

  * update `mapchete_eo.processes.merge_rasters` to merge multiple geometries for single raster, to have one multigeometry for one raster

2025.1.1 - 2025-01-22
----------------------

* core

  * update `mapchete_eo.processes.merge_rasters` to work with `rasters` and `vectors` as input that handle the merge process
  * use more `mapchete.geometry.reproject_geometry` in the package, to align with latest `mapchete` versions better

* CI/CD

  * use base image `2025.1.1` for testing


2025.1.0 - 2025-01-07
----------------------

* core

  * `io.products.merge_products()`: reduce memory footprint when merging multiple products using `MergeMethod.average`


2024.12.0 - 2024-12-05
----------------------

* core

  * `io.assets.read_mask_as_raster()`: fix masking of `aiohttp.ClientResponseError` where some tool raises a generic `Exception` instead of the original `ClientResponseError`


2024.11.6 - 2024-11-26
----------------------

* core

  * `io.assets.asset_to_np_array()`: get asset path early to catch and raise an `AssetMissing` error


2024.11.5 - 2024-11-25
----------------------

* core

  * `platforms.sentinel2.metadata_parser.ViewingIncidenceAngle.merge_detectors()`: raise `CorruptedProductMetadata` if no detector data is available
  * `io.products.merge_products()` try to catch `StopIteration` early


2024.11.4 - 2024-11-22
----------------------

* core

  * `platforms.sentinel2.metadata_parser.open_xml()`: add retry decorator to XML opener
  * `io.products.merge_products()` catch `StopIteration` exception and continue

* CLI

  * `s2-jp2-static-catalog`: account for empty day directory

* packaging

  * use base image `2024.11.0` for testing


2024.11.3 - 2024-11-19
----------------------

* core

  * fix bug where process fails when there are no slices over tile


2024.11.2 - 2024-11-18
----------------------

* core

  * `platforms.sentinel2.brdf`:

    * whole refacturing of module
    * brought back legacy `HLS`
    * added `RossThick` model

  * BRDF configuration: set `per_detector_correction` to `False` on default

  * `io.assets.read_levelled_cube()`: improved log messages

* CLI

  * `mapchete eo static-catalog`: now updates existing catalog instead of replacing it


2024.11.1 - 2024-11-08
----------------------

* core

  * `io.read_levelled_cube_to_np_array()`: try to stuff memory leaks; run `gc.collect()` after each slice iteration


2024.11.0 - 2024-11-07
----------------------

* core

  * `io.read_levelled_cube_to_np_array()`: refactor, skip slices if they won't provide new pixels; make `grid` mandatory; add `out_dtype` and `out_fill_value` kwargs
  * `platforms.sentinel2.product.Product` `get_mask()` and `read_np_array()`: add `target_mask` kwarg


2024.10.5 - 2024-10-28
----------------------

* core

  * Sentinel-2:

    * move `brdf` module to `platforms.sentinel2` and do a whole restructuring
    * add BRDF correction variant which uses a combined angle grid instead of a per-detector grid approach
    * optionally scale reflectance values using log10 before correcting them
    * add bandpass adjustment option

  * `io.assets`: better check output profile before attempting to convert an asset


2024.10.4 - 2024-10-23
----------------------

* core

  * Sentinel-2: only call `_cache_reset()` if metadata object was initialized


2024.10.3 - 2024-10-22
----------------------

* cli
  
  * Add `--out_dtype` option to `s2-rgb` CLI operation for debuging
  * Add `--brdf-log10` flag to `s2-rgb` CLI operation for debugging

* core
  
  * Added `_apply_sentinel2_bandpass_adjustment` to `read_np_array` in `platforms.sentinel2.product.S2Product` class, toggle with: `apply_sentinel2_bandpass_adjustment` bool flag
  * cleanup and update the `brdf` function chain, add some typing
  * the `brdf` now uses only single model based on following sources:

    * https://sci-hub.st/https://ieeexplore.ieee.org/document/8899868
    * https://sci-hub.st/https://ieeexplore.ieee.org/document/841980
    * https://custom-scripts.sentinel-hub.com/sentinel-2/brdf/#

  * added with flag into BRDFModelConfig as `log10_bands_scale_flag` for: `brdf` original band scaling is now converting the bands to `log10` and applying the `brdf` correction on top of the `log10` converted data
  

2024.10.2 - 2024-10-21
----------------------

* core

  * Sentinel-2: clear product & metadata caches in between each slice read


2024.10.1 - 2024-10-21
----------------------

* core

  * Sentinel-2: make sure pydantic can parse scene classification names from configuration


2024.10.0 - 2024-10-18
----------------------

* core

  * add `brdf_weight` and `scl_classes` options to Sentinel-2 BRDF correction
  * `S2Metadata`: return pydantic models instead of dicts on some angle properties


2024.9.3 - 2024-09-27
---------------------

* core

  * add configuration flags to cache certain QI and mask files before reading them to avoid unnecessary requests

* packaging

  * remove eoxcloudless processes from pyproject.toml


2024.9.2 - 2024-09-23
---------------------

* core

  * `mapchete_eo.search.stac_search`: fix chunked search


2024.9.1 - 2024-09-18
---------------------

* core

  * `mapchete_eo.processes`: remove all `eoxcloudless_*` processes


2024.9.0 - 2024-09-12
---------------------

* core

  * `mapchete_eo.io.assets._read_vector_mask()`: fix deprecation bug due to Fiona changing error messages
  * add `processes.eoxcloudless_scl_mosaic` process
  * replace `mp.clip` with `clip_array_with_vector` from latest mapchete version
  * `mapchete_eo.processes`: use typing to define inputs

* CI

  * use `2024.9.1` docker-base mapchete image for tests

* packaging

  * use `ruff` instead of `black`, `flake8` and `isort`


2024.7.0 - 2024-07-25
---------------------

* core
  * fix import for `BaseGeometry` in ``stac_static.py``, now imported from `shapely.geometry.base` and not from `mapchete.types`
  * replace `mp.clip` with `from mapchete.io.raster.array import clip_array_with_vector` in processes `rgb_map` and `sentinel2_color_correction`

* CI
  * use `2024.7.0` docker-base mapchete image for tests

* packaging
  * bump `mapchete` to 2024.7.1
  * align dependencies `requirements.txt`, `requirements-dev.txt` with `pyproject.toml` with `hatch` package
    * `hatch dep show requirements`
    * `hatch dep show requirements >> requirements.txt`  
  * `requrements-dev.txt` still need to be managed manually when required


2024.6.0 - 2024-06-03
---------------------

* core
  * `processes.eoxcloudless_sentinel2_color_correction`: fix 3-band issue


2024.5.9 - 2024-05-23
---------------------

* core
  * `image_operations`: add typing
  * `image_operations.compositing.to_rgba`: fix cases where mask of masked_array is a single bool value


2024.5.8 - 2024-05-23
---------------------

* core
  * `processes.eoxcloudless_sentinel2_color_correction`: streamline code; enable configuration of smooth operations


2024.5.7 - 2024-05-22
---------------------

* core
  * `processes.eoxcloudless_sentinel2_color_correction`: add optional `glacier_mask` input and fix nodata masking

* CLI
  * `s2-find-broken-products`: add option to dump product thumbnails


2024.5.6 - 2024-05-16
---------------------

* core
  * `geometry.buffer_antimeridian_safe()`: don't raise `EmptyFootprintException` on emtpy output (sub)geometry



2024.5.5 - 2024-05-14
---------------------

* core
  * `geometry.custom_transform()`: try to make output geometry valid


2024.5.4 - 2024-05-14
---------------------

* core
  * `io.geometry.buffer_antimeridian_safe()`: avoid recursion by buffering subpolygons separately instead of again trying to buffer a MultiPolygon


2024.5.3 - 2024-05-08
---------------------

* core
  * move `io.geometry` module to root
  * `geometry.custom_transform()`: enable handling empty geometry
  * added `exceptions.ItemGeometryError` and raise it when parsing geometries of STAC items fails


2024.5.2 - 2024-05-07
---------------------

* core
  * add blacklist capability for `S2AWS_JP2` archive
  * fix antimeridian-crossing footprint reprojection issue


2024.5.1 - 2024-05-07
---------------------

* core
  * add static search catalog for antimeridian products
  * `io.assets.read_mask_as_raster()`
    * use `read_raster_window()` when `dst_grid` is given
    * optionally cache file locally before reading by activating `cachde_reading` flag


2024.5.0 - 2024-05-03
---------------------

* core
  * add retries around various `rasterio_open` calls


2024.4.3 - 2024-04-26
---------------------

* core
  * repair footprints if required


2024.4.2 - 2024-04-19
---------------------

* core
  * S2AWS_JP2: apply offset if required


2024.4.1 - 2024-04-19
---------------------

* core
  * determine `boa_offset_applied` also for S2AWS_JP2 items


2024.4.0 - 2024-04-18
---------------------

* core
  * make `UTMSearchCatalog` handle empty areas

* CLI
  * add `s2-find-broken-products` subcommand
  * `s2-verify`: extend verification by analyzing outliers in thumbnail


2024.3.6 - 2024-03-29
---------------------

* core
  * `S2Product.get_mask()`: don't fail on EmptyFootprintException after buffering footprint


2024.3.5 - 2024-03-27
---------------------

* core
  * `MaskConfig` was extended by the `footprint_buffer_m` value (default: -500) to clip Sentinel-2 products
  * extended CLI to be able to handle `S2AWS_JP2` archive
  * streamline STAC items from AWS JP2 archive to match the naming schemes of AWS COG; also add datastrip_id
  * added much typing information on the go
  * replaced `Catalog` abstract base class with `CatalogProtocol` protocol
  * enabled `UTMSearchCatalog` to write static STAC catalog (used to create testdata fixtures over Antimeridian)
  * improved `UTMSearchCatalog` search algorithm by querying multiple S2Tiles per day at once


2024.3.4 - 2024-03-26
---------------------

* core
  * fix `color_correction.py` structure, dtypes and operations order


2024.3.3 - 2024-03-25
---------------------

* core
  * add `image_operations.sigmodial` to `image_operations` and `image_operations.color_correction` submodule to mimic rio color even further and to have eox control over its array operations
  * add `sigmodial_flag: bool = False`, `sigmodial_contrast: int = 0` and `sigmodial_bias: float = 0.0` to `RGBCompositeConfig` to have these for mapchete color corrections  


2024.3.2 - 2024-03-21
---------------------

* core
  * add `utm_search.py` and `s2_mgrs` into utm_search
  * `UTMSearchConfig` for a new archive named `S2AWS_JP2`
    * This searches the STAC items directly via Bucket
  * Antimeridian products focus to aleviate Element84 missing footprints and products over Antimeridian
  * add tests for the above


2024.3.1 - 2024-03-19
---------------------

* core
  * fix handling of empty footprints in `merge_rasters()`


2024.3.0 - 2024-03-18
---------------------

* core
  * add `merge_rasters()` and `eoxcloudless_mosaic_merge()` processes


2024.2.6 - 2024-02-20
---------------------

* core
  * `merge_products()`: skip products with missing assets
  * added `s2-verify` subcommand
  * blacklist: add log message if blacklist cannot be found & only add item if it does not already exist in blacklist


2024.2.5 - 2024-02-16
---------------------

* core
  * update/fix `eoxcloudless_rgb_map`


2024.2.4 - 2024-02-15
---------------------

* core
  * make sure arrays in `eoxcloudless_rgb_map` are `uint8`
  * fix `to_rgba` 3 band version, take into account all 3 bands to make sure

2024.2.3 - 2024-02-15
---------------------

* core
  * add `mosaic_mask` to `eoxcloudless_rgb_map` mapchete process

2024.2.2 - 2024-02-15
---------------------

* core
  * add `eoxcloudless_rgb_map`mapchete process


2024.2.1 - 2024-02-13
---------------------

* core
  * make `preprocessing_tasks=False` the default
  * add `BRDFError` to `CorruptedProduct` and add product to blacklist, also when caching


2024.2.0 - 2024-02-12
---------------------

* core
  * add option `preprocessing_tasks` to deactivate preprocessing tasks
  * make `S2Metadata` load lazily when initializing `S2Product`
  * add `area` parameter to limit AOI of EO cube


2024.1.5 - 2024-01-17
---------------------

* core
  * fix `Brightness` and `Saturation` HSV color correction operations in `color_correct`
  * larger radius for water smoothing in `smooth_water` of `eoxcloudless_sentinel2_color_correction` process


2024.1.4 - 2024-01-15
---------------------

* core
  * `io.path`: add `open_json` with retry mechaniym (for tileInfo.json)


2024.1.3 - 2024-01-12
---------------------

* core
  * raise `exceptions.AssetMissing` error if asset file cannot be found
  * `io.products.merge_products()`: account for potentially broken products


2024.1.2 - 2024-01-11
---------------------

* core
  * don't raise exception if no preprocessing tasks are available


2024.1.1 - 2024-01-11
---------------------
* CI/CD
  * use `privileged` tag for codecheck stage

* core
  * also retry on `ServerDisconnectedError` in `io.open_xml`


2024.1.0 - 2024-01-04
---------------------
* CI/CD
  * use `mapchete` image tag `2024.1.0`

* core
  * align `retry` args to match latest mapchete release

* packaging
  * bump `mapchete` to `2024.1.0`  


2023.12.3 - 2023-12-15
----------------------

NOTE: no code changes here, just added missing changelog entries for 2023.12.2

* core

  * fixed S3 cache
  * enable product blacklist
  * lazily generate `pystac.Item` when preprocessing to save memory


2023.12.2 - 2023-12-15
----------------------

* core

  * use `GridProtocol`, `Grid` and resampling functions from mapchete core package


2023.12.1 - 2023-12-11
----------------------

* core

  * `product.EOProduct` now loads `item` lazily


2023.12.0 - 2023-12-11
----------------------

* CI/CD

  * use `mapchete` image tag `2023.12.1`
  * use `podman` instead of `docker`

* core

  * fix mask buffer dtype


2023.11.0 - 2023-11-28
----------------------

* CI/CD

  * use `mapchete` image tag `2023.11.0` with the same mapchete version

* core

  * add `read_masks` and `buffer_array` functions and tests to have more mask handling options

* packaging

  * bump `mapchete` to `2023.11.0`


2023.10.0 - 2023-10-20
----------------------

first release!

* basic functionality

  *  Sentinel-2 processing
  *  Generic EO product processing
  *  BRDF correction for Sentinel-2
  *  using STAC to read and store archives
  *  internally using xarrays where applickable
  *  more modular code
  *  fully typed
  *  optimized test suite (i.e. most tests use cached testdata)
  *  using pydantic to pass on settings
