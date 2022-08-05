from mapchete_eo.archives.base import Archive

# NOTE:
#
# * COG and JP2 archives differ in that the JP2 files don't have a nodata value encoded!


class S2AWSCOGArchive(Archive):

    catalog_name = "E84Sentinel2COGs"
    storage_kwargs = {
        "baseurl": "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/"
    }


class S2AWSJP2Archive(Archive):

    catalog_name = "SinergiseSentinel2"
    storage_kwargs = {}
