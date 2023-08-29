Test Data Generation
====================

Sentinel-2 full products
------------------------

```bash
$ mapchete eo static-catalog \
    --bounds 16 46 16.1 46.1 \
    --start-time 2023-08-10 \
    --end-time 2023-08-13 \
    --assets red,green,blue \
    --assets-dst-resolution 120m \
    --assets-dst-rio-profile jp2_lossy \
    --copy-metadata \
    tests/testdata/sentinel2/full_products/
```