def execute(mp, assets=None):
    with mp.open("inp") as inp:
        return inp.read(assets=assets)
