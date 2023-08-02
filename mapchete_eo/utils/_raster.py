from mapchete_eo.settings import SENTINEL2_BAND_INDEXES


def to_band_idx(bname, product):
    if isinstance(bname, int):
        return bname
    elif isinstance(bname, str):
        for k, v in SENTINEL2_BAND_INDEXES[product["properties"]["level"]].items():
            if bname.lower() == v.lower().split("_")[0]:
                return k
        else:
            raise ValueError(f"band name {bname} cannot be mapped to index")
    else:
        raise ValueError("band name must be an integer or a string")
