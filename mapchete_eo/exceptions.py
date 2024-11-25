"""Custom exceptions."""

from mapchete.errors import MapcheteNodataTile


class EmptyFootprintException(Exception):
    """Raised when footprint is empty."""


class EmptySliceException(Exception):
    """Raised when slice is empty."""


class EmptyProductException(EmptySliceException):
    """Raised when product is empty."""


class EmptyStackException(MapcheteNodataTile):
    """Raised when whole stack is empty."""


class EmptyFileException(Exception):
    """Raised when no bytes are downloaded."""


class IncompleteDownloadException(Exception):
    """ "Raised when the file is not downloaded completely."""


class InvalidMapcheteEOCollectionError(Exception):
    """ "Raised for unsupported collections of Mapchete EO package."""


class EmptyCatalogueResponse(Exception):
    """Raised when catalogue response is empty."""


class CorruptedGTiffError(Exception):
    """Raised when GTiff validation fails."""


class BRDFError(Exception):
    """Raised when BRDF grid cannot be calculated."""


class AssetError(Exception):
    """Generic Exception class for Assets."""


class AssetMissing(AssetError, FileNotFoundError):
    """Raised when a product asset should be there but isn't."""


class AssetEmpty(AssetError):
    """Raised when a product asset should contain data but is empty."""


class AssetKeyError(AssetError, KeyError):
    """Raised when an asset name cannot be found in item."""


class PreprocessingNotFinished(Exception):
    """Raised when preprocessing tasks have not been fully executed."""


class AllMasked(Exception):
    """Raised when an array is fully masked."""


class NoSourceProducts(MapcheteNodataTile, ValueError):
    """Raised when no products are available."""


class CorruptedProduct(Exception):
    """Raised when product is damaged and cannot be read."""


class CorruptedProductMetadata(CorruptedProduct):
    """Raised when EOProduct cannot be parsed due to a metadata issue."""


class CorruptedSlice(Exception):
    """Raised when all products in a slice are damaged and cannot be read."""


class ItemGeometryError(Exception):
    """Raised when STAC item geometry cannot be resolved."""
