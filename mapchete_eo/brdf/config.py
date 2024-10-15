from enum import Enum


class BRDFModels(str, Enum):
    none = "none"
    HLS = "HLS"
    HLS_alt = "HLS_alt"
    sen2agri = "sen2agri"
    combined = "combined"
    default = "HLS"


# Source for bands outside of RGBNIR range:
# https://www.sciencedirect.com/science/article/pii/S0034425717302791
# https://www.semanticscholar.org/paper/Adjustment-of-Sentinel-2-Multi-Spectral-Instrument-Roy-Li/be90a03a19c612763f966fae5290222a4b76bba6
F_MODIS_PARAMS = {
    1: (0.0774, 0.0079, 0.0372),
    2: (0.0774, 0.0079, 0.0372),
    3: (0.1306, 0.0178, 0.0580),
    4: (0.1690, 0.0227, 0.0574),
    5: (0.2085, 0.0256, 0.0845),
    6: (0.2316, 0.0273, 0.1003),
    7: (0.2599, 0.0294, 0.1197),
    8: (0.3093, 0.0330, 0.1535),
    9: (0.3093, 0.0330, 0.1535),
    10: (0.3201, 0.0471, 0.1611),
    11: (0.3430, 0.0453, 0.1154),
    12: (0.2658, 0.0387, 0.0639),
}

# MODIS BANDS LEGEND:
# 1: Red (B04 S2-Band)
# 2: NIR (B08 S2-Band)
# 3: Blue (B02 S2-Band)
# 4: Green (B03 S2-Band)
# 5: SWIR (B10 S2-Band)
# 6: SWIR (B11 S2-Band)
# 7: SWIR (B12 S2-Band)

F_MODIS_PARAMS_WATER = {
    # 1: (0.0774, 0.0079, 0.0372),
    # gdalinfo -stats HDF4_EOS:EOS_GRID:"/home/ungarj/Downloads/MCD43A1.A2024001.h32v11.061.2024010142818.hdf":MOD_Grid_BRDF:BRDF_Albedo_Parameters_Band3 | grep STATISTICS_MEAN
    #     STATISTICS_MEAN=45.749820822192
    #     STATISTICS_MEAN=18.862013316001
    #     STATISTICS_MEAN=3.6893748795183
    2: (0.045749820822192, 0.018862013316001, 0.0036893748795183),
    # 2: (0.0774, 0.0079, 0.0372),
    # gdalinfo -stats HDF4_EOS:EOS_GRID:"/home/ungarj/Downloads/MCD43A1.A2024001.h32v11.061.2024010142818.hdf":MOD_Grid_BRDF:BRDF_Albedo_Parameters_Band4 | grep STATISTICS_MEAN
    #     STATISTICS_MEAN=36.64969203859
    #     STATISTICS_MEAN=16.622094434892
    #     STATISTICS_MEAN=4.1738483036108
    3: (0.03664969203859, 0.016622094434892, 0.0041738483036108),
    # 3: (0.1306, 0.0178, 0.0580),
    # gdalinfo -stats HDF4_EOS:EOS_GRID:"/home/ungarj/Downloads/MCD43A1.A2024001.h32v11.061.2024010142818.hdf":MOD_Grid_BRDF:BRDF_Albedo_Parameters_Band1 | grep STATISTICS_MEAN
    #     STATISTICS_MEAN=38.140581101301
    #     STATISTICS_MEAN=29.048258024416
    #     STATISTICS_MEAN=7.0272254956754
    4: (0.038140581101301, 0.029048258024416, 0.0070272254956754),
    # 4: (0.1690, 0.0227, 0.0574),
    # 5: (0.2085, 0.0256, 0.0845),
    # 6: (0.2316, 0.0273, 0.1003),
    # 7: (0.2599, 0.0294, 0.1197),
    # gdalinfo -stats HDF4_EOS:EOS_GRID:"/home/ungarj/Downloads/MCD43A1.A2024001.h32v11.061.2024010142818.hdf":MOD_Grid_BRDF:BRDF_Albedo_Parameters_Band2 | grep STATISTICS_MEAN
    #     STATISTICS_MEAN=68.706919752494
    #     STATISTICS_MEAN=64.399508243889
    #     STATISTICS_MEAN=20.155743112654
    8: (0.068706919752494, 0.064399508243889, 0.020155743112654),
    # 8: (0.3093, 0.0330, 0.1535),
    # 9: (0.3093, 0.0330, 0.1535),
    # 10: (0.3201, 0.0471, 0.1611),
    # 11: (0.3430, 0.0453, 0.1154),
    # 12: (0.2658, 0.0387, 0.0639),
}

F_MODIS_PARAMS.update(F_MODIS_PARAMS_WATER)
