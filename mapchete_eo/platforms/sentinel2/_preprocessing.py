import logging
import numpy as np
from retry import retry
from mapchete.path import MPath
from mapchete.io.raster import ReferencedRaster

from mapchete_eo.platforms.sentinel2.brdf import (
    cache_brdf_correction_grids,
    cache_brdf_angles,
)
from mapchete_eo.platforms.sentinel2.metadata_parser import (
    S2Metadata,
)
from mapchete_eo.utils._raster import to_band_idx
from mapchete_eo.utils.tools import _uncached_files, get_product_cache_path
from mapchete_eo.settings import (
    MP_EO_IO_RETRY_SETTINGS,
    SENTINEL2_BAND_INDEXES,
    VALID_PREPROCESSING_EXCEPTIONS,
)

logger = logging.getLogger(__name__)


# TODO: update functions etc. split the whole thing into something smaller maybe
@retry(logger=logger, **MP_EO_IO_RETRY_SETTINGS)
def prepare_product_assets(
    product=None,
    config=None,
    requester_payer=None,
    process_bounds=None,
    process_crs=None,
):
    raise NotImplementedError
    # try:
    #     s2_metadata = S2Metadata.from_metadata_xml(
    #         product["properties"]["metadata_xml"],
    #         processing_baseline=product["properties"].get("s2:processing_baseline"),
    #         boa_offset_applied=product["properties"].get(
    #             "earthsearch:boa_offset_applied", False
    #         ),
    #     )
    # except FileNotFoundError:
    #     logger.debug(
    #         "%s not found, skipping product", product["properties"]["metadata_xml"]
    #     )
    #     # not optimal to return None if product should be skipped but works for now
    #     return

    # # add specific Sentinel-2 metadata
    # product["properties"]["slice_id"] = s2_metadata.datastrip_id
    # product["properties"]["processing_baseline"] = s2_metadata.processing_baseline
    # product["properties"]["reflectance_offset"] = s2_metadata.reflectance_offset

    # # save some info about brdf settings for fallbacks in case of errors
    # if config["brdf"]:
    #     product["properties"]["brdf"] = config["brdf"]

    # if config["cache"]:
    #     product_cache_path = get_product_cache_path(product=product, config=config)
    #     try:
    #         existing_files = MPath(product_cache_path).ls()
    #     except FileNotFoundError:
    #         MPath(product_cache_path).makedirs()
    #         existing_files = []

    #     # cache BRDF correction grids
    #     if config["brdf"]:
    #         logger.debug("prepare BRDF model for product")

    #         # detector footprints
    #         resolution = config["brdf"]["resolution"]
    #         model = config["brdf"]["model"]
    #         out_paths = {
    #             to_band_idx(band_idx, product): MPath(product_cache_path).joinpath(
    #                 f"brdf_{model}_{band_idx}_{resolution}.tif"
    #             )
    #             for band_idx in config["brdf"]["bands"]
    #         }
    #         uncached = _uncached_files(
    #             existing_files=existing_files,
    #             out_paths=out_paths,
    #             remove_invalid=config["cache"]["cached_files_validation"],
    #         )
    #         if uncached:
    #             try:
    #                 cache_brdf_correction_grids(
    #                     s2_metadata=s2_metadata,
    #                     resolution=resolution,
    #                     model=model,
    #                     out_paths=out_paths,
    #                     product_id=product["id"],
    #                     uncached=uncached,
    #                     check_cached_files_exist=config["cache"][
    #                         "check_cached_files_exist"
    #                     ],
    #                     cached_files_validation=config["cache"][
    #                         "cached_files_validation"
    #                     ],
    #                 )
    #             except VALID_PREPROCESSING_EXCEPTIONS as exc:
    #                 return exc
    #         else:
    #             logger.debug("BRDF model for all bands already exists.")
    #         product["properties"].update(brdf_paths=out_paths)

    #     # cache angles
    #     if config["cache"].get("angles"):
    #         logger.debug("cache angle bands")
    #         out_paths = {
    #             angle: MPath(product_cache_path).joinpath(
    #                 f"{angle}{f'_{resolution}' if 'view' in angle else ''}.tif",
    #             )
    #             for angle in config["cache"]["angles"]
    #         }
    #         uncached = _uncached_files(
    #             existing_files=existing_files,
    #             out_paths=out_paths,
    #             remove_invalid=config["cache"]["cached_files_validation"],
    #         )
    #         if uncached:
    #             cache_brdf_angles(
    #                 s2_metadata=s2_metadata,
    #                 resolution=resolution,
    #                 out_paths=out_paths,
    #                 uncached=uncached,
    #                 check_cached_files_exist=config["cache"][
    #                     "check_cached_files_exist"
    #                 ],
    #                 cached_files_validation=config["cache"]["cached_files_validation"],
    #             )
    #         else:
    #             logger.debug("BRDF angle grids already exists.")
    #         product["properties"].update(**out_paths)

    #     # cache cloudmasks
    #     if config["with_cloudmasks"]:
    #         logger.debug("prepare cloud masks")
    #         if config["cache"]["cloudmask_format"] == "GTiff":
    #             resolution = config["cache"]["cloudmask_raster_resolution"]
    #             out_path = MPath(product_cache_path).joinpath(
    #                 f"cloudmask_{resolution}.tif"
    #             )
    #             uncached = _uncached_files(
    #                 existing_files=existing_files,
    #                 out_paths=out_path,
    #                 remove_invalid=config["cache"]["cached_files_validation"],
    #             )
    #             if uncached:
    #                 cache_cloudmask_raster(
    #                     s2_metadata=s2_metadata,
    #                     resolution=resolution,
    #                     out_path=out_path,
    #                     check_cached_files_exist=config["cache"][
    #                         "check_cached_files_exist"
    #                     ],
    #                     cached_files_validation=config["cache"][
    #                         "cached_files_validation"
    #                     ],
    #                 )
    #             product["properties"].update(cloudmask=out_path)

    #         elif config["cache"]["cloudmask_format"] == "GPKG":
    #             out_path = MPath(product_cache_path).joinpath("cloudmask.gpkg")
    #             uncached = _uncached_files(
    #                 existing_files=existing_files, out_paths=out_path
    #             )
    #             if uncached:
    #                 cache_cloudmask_vector(
    #                     s2_metadata=s2_metadata,
    #                     out_path=out_path,
    #                 )
    #             product["properties"].update(cloudmask=out_path)
    #     else:
    #         product["properties"].update(cloudmask=[])

    #     # cache metadata bands
    #     for i in ["qi_cld", "qi_snw", "aot"]:
    #         if config["cache"][i]:
    #             in_path = band_index_to_path(i, product)
    #             out_path = MPath(product_cache_path).joinpath(i + ".tif")
    #             uncached = _uncached_files(
    #                 existing_files=existing_files,
    #                 out_paths=out_path,
    #                 remove_invalid=config["cache"]["cached_files_validation"],
    #             )
    #             if uncached:
    #                 _to_cog(
    #                     in_path=in_path,
    #                     out_path=out_path,
    #                     requester_payer="requester"
    #                     if in_path.startswith("s3://sentinel-s2-l2a/")
    #                     else requester_payer,
    #                     timeout=config["remote_timeout"],
    #                 )
    #             product["properties"][i] = out_path

    #         # cache bands

    #     if config["cache"]["bands"] and bands_will_be_cached(
    #         footprint=product["geometry"],
    #         process_bounds=process_bounds,
    #         cache_perc=config["cache"]["intersection_percent"],
    #         cache_path=config["cache"]["path"],
    #         cache_max_disk_usage=config["cache"]["max_disk_usage"],
    #         cache_max_cloud_percent=config["cache"]["max_cloud_percent"],
    #         cloudcover=product["properties"]["cloud_cover"],
    #     ):
    #         if config["format"].upper() == "S2AWS_COG":
    #             logger.warning(
    #                 "It is not recommended to cache bands when using S2AWS COG!"
    #             )

    #         logger.debug("cache bands for product %s", product["id"])
    #         band_indexes = SENTINEL2_BAND_INDEXES[config["level"]]

    #         # cache bands as GTiffs
    #         for i, bid in band_indexes.items():
    #             if i in config["cache"]["bands"]:
    #                 out_path = MPath(product_cache_path).joinpath(bid + ".tif")
    #                 uncached = _uncached_files(
    #                     existing_files=existing_files,
    #                     out_paths=out_path,
    #                     remove_invalid=config["cache"]["cached_files_validation"],
    #                 )
    #                 if uncached:
    #                     _to_cog(
    #                         in_path=product["properties"]["band_paths"][i],
    #                         out_path=out_path,
    #                         requester_payer=requester_payer,
    #                         timeout=config["remote_timeout"],
    #                     )
    #                 product["properties"]["band_paths"][i] = out_path
    #         # cache SCL mask if available
    #         if (
    #             config["with_scl"]
    #             and product["properties"].get("scl_mask", None) is not None
    #         ):
    #             out_path = MPath(product_cache_path).joinpath("SCL_20m.tif")
    #             uncached = _uncached_files(
    #                 existing_files=existing_files,
    #                 out_paths=out_path,
    #                 remove_invalid=config["cache"]["cached_files_validation"],
    #             )
    #             if uncached:
    #                 _to_cog(
    #                     in_path=product["properties"]["scl_mask"],
    #                     out_path=out_path,
    #                     requester_payer=requester_payer,
    #                     timeout=config["remote_timeout"],
    #                 )
    #             product["properties"]["scl_mask"] = out_path

    # else:
    #     if config["with_cloudmasks"]:
    #         logger.debug("prepare cloud masks")
    #         if config["cloudmask_memory_format"] == "raster":
    #             resolution = config["cloudmask_memory_raster_resolution"]
    #             bands = []
    #             for band_idx, mask_type in enumerate(SENTINEL2_CLOUDMASK_TYPES, 1):
    #                 features = [
    #                     f["geometry"]
    #                     for f in s2_metadata.cloud_mask(mask_type=mask_type)
    #                 ]
    #                 if features:
    #                     logger.debug(f"burn {mask_type} cloudmask features to raster")
    #                     bands.append(
    #                         geometry_mask(
    #                             features,
    #                             s2_metadata.shape(resolution),
    #                             s2_metadata.transform(resolution),
    #                             all_touched=False,
    #                             invert=True,
    #                         )
    #                     )
    #                 else:
    #                     logger.debug(f"no {mask_type} cloudmask features found")
    #                     bands.append(
    #                         np.zeros(s2_metadata.shape(resolution), dtype="uint8")
    #                     )
    #             cloudmasks = ReferencedRaster(
    #                 data=np.stack(bands),
    #                 affine=s2_metadata.transform(resolution),
    #                 bounds=s2_metadata.bounds,
    #                 crs=s2_metadata.crs,
    #             )
    #         else:
    #             cloudmasks = [
    #                 dict(
    #                     geometry=mapping(
    #                         reproject_geometry(
    #                             shape(feature["geometry"]).buffer(0),
    #                             src_crs=s2_metadata.crs,
    #                             dst_crs=process_crs,
    #                         )
    #                     ),
    #                     properties=feature["properties"],
    #                     id=feature["id"],
    #                 )
    #                 for feature in expand_to_polygon_features(s2_metadata.cloud_mask())
    #             ]
    #             logger.debug("%s cloudmask geometries found", len(cloudmasks))
    #         product["properties"].update(cloudmask=cloudmasks)
    #     else:
    #         product["properties"].update(cloudmask=[])

    #     # cache BRDF correction grids
    #     if config["brdf"]:
    #         from s2brdf.brdf import get_brdf_param
    #         from s2brdf.tools import get_sun_angle_array

    #         logger.debug("prepare BRDF model for product")
    #         _, (bottom, top) = transform(
    #             s2_metadata.crs,
    #             "EPSG:4326",
    #             [s2_metadata.bounds[0], s2_metadata.bounds[2]],
    #             [s2_metadata.bounds[1], s2_metadata.bounds[3]],
    #         )
    #         resolution = config["brdf"]["resolution"]
    #         model = config["brdf"]["model"]
    #         sun_zenith_angle = get_sun_angle_array(
    #             min_lat=bottom,
    #             max_lat=top,
    #             shape=s2_metadata.sun_angles["zenith"]["array"].shape,
    #         )
    #         product["properties"]["brdf_paths"] = {}
    #         for band in config["brdf"]["bands"]:
    #             band_idx = to_band_idx(band, product)
    #             correction_grid = ReferencedRaster(
    #                 data=get_brdf_param(
    #                     band_idx=band_idx,
    #                     out_shape=s2_metadata.shape(resolution),
    #                     out_transform=s2_metadata.transform(resolution),
    #                     product_crs=s2_metadata.crs,
    #                     sun_angles=s2_metadata.sun_angles,
    #                     detector_footprints=s2_metadata.detector_footprints(band_idx),
    #                     viewing_incidence_angles=s2_metadata.viewing_incidence_angles(
    #                         band_idx
    #                     ),
    #                     sun_zenith_angle=sun_zenith_angle,
    #                     model=model,
    #                 ),
    #                 affine=s2_metadata.transform(resolution),
    #                 bounds=s2_metadata.bounds,
    #                 crs=s2_metadata.crs,
    #             )
    #             product["properties"]["brdf_paths"][band_idx] = correction_grid

    # return product
