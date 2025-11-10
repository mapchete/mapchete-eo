def execute(mp):
    with mp.open("inp") as src:
        src.read(assets=["data"])
    return "empty"
