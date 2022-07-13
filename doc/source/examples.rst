Examples
========


S2AWS
-----

.. code-block:: yaml

    input:
        s2:
            format: S2AWS
            start_time: 2018-04-02  # required
            end_time: 2018-04-03  # required
            with_cloudmasks: True  # also get cloud masks
            metadata_concurrency: True  # parse source metadata concurrently
            metadata_concurrency_threads: 4  # use n threads
            footprint_buffer: -500  # negative buffer applied to footprints (default: -500)
            max_products: 4500  # maximum number of products to be fetched
            first_granule_only: False  # only use first granule of each day (for Sentinel-2)
            cache:  # optional
                path: cache  # path to cache
                bands: [1]  # specify which bands to cache
                keep: true  # don't delete cached data after process is finished
                intersection_percent: 0  # only cache products with minimum intersection
                max_cloud_percent: 10  # only cache products with maximum cloud cover
                max_disk_usage: 90  # stop further caching if disk is n% full


S2Mundi
-------

.. code-block:: yaml

    input:
        s2:
            format: S2Mundi
            start_time: 2018-04-02  # required
            end_time: 2018-04-03  # required
            level: L1C  # or 'L2A' for Level 2A data
            with_cloudmasks: True  # also get cloud masks
            metadata_concurrency: True  # parse source metadata concurrently
            metadata_concurrency_threads: 4  # use n threads
            footprint_buffer: -500  # negative buffer applied to footprints (default: -500)
            max_products: 4500  # maximum number of products to be fetched
            first_granule_only: False  # only use first granule of each day (for Sentinel-2)
            cache:  # optional
                path: cache  # path to cache
                bands: [1]  # specify which bands to cache
                keep: true  # don't delete cached data after process is finished
                intersection_percent: 0  # only cache products with minimum intersection
                max_cloud_percent: 10  # only cache products with maximum cloud cover
                max_disk_usage: 90  # stop further caching if disk is n% full

S1Mundi
-------

.. code-block:: yaml

    input:
        s2:
            format: S1Mundi
            start_time: 2018-04-02  # required
            end_time: 2018-04-03  # required
            level: L1_
            sensormode: IW
            producttype: GRD
            metadata_concurrency: True  # parse source metadata concurrently
            metadata_concurrency_threads: 4  # use n threads
            footprint_buffer: -500  # negative buffer applied to footprints (default: -500)
            max_products: 4500  # maximum number of products to be fetched
            first_granule_only: False  # only use first granule of each day (for Sentinel-2)
            cache:  # optional
                path: cache  # path to cache
                resampling: bilinear_interpolation  # interpolation used when regridding data
                sar_calibration: gamma0
                tnr: true
                keep: true  # don't delete cached data after process is finished
                max_disk_usage: 90  # stop further caching if disk is n% full
                zoom: 13