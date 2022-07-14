class Catalog:
    @property
    def items(self):
        raise NotImplementedError("catalog class has not implemented this property")

    @property
    def eo_bands(self):
        raise NotImplementedError("catalog class has not implemented this property")
