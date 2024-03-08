from mapchete_eo.search.s2_mgrs import S2Tile, s2_tiles_from_bounds


def test_mgrs():
    tiles = s2_tiles_from_bounds(0.72796, 47.36041, 3.68207, 50.24650, crs="EPSG:4326")
    for tile in tiles:
        print(tile)
    assert set(tiles) == set(
        [
            S2Tile.from_tile_id("31UCR"),
            S2Tile.from_tile_id("31UDR"),
            S2Tile.from_tile_id("31UER"),
            S2Tile.from_tile_id("31UEQ"),
            S2Tile.from_tile_id("31UEP"),
            S2Tile.from_tile_id("31UDP"),
            S2Tile.from_tile_id("31UDQ"),
            S2Tile.from_tile_id("31UCQ"),
            S2Tile.from_tile_id("31TCN"),
            S2Tile.from_tile_id("31TDN"),
            S2Tile.from_tile_id("31TEN"),
        ]
    )
