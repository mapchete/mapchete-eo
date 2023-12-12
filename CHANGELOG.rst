#########
Changelog
#########

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
