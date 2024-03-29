#########
Changelog
#########


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
