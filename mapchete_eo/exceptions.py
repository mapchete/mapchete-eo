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
    """Raised when calculated BRDF grid is empty."""


class MissingAsset(Exception):
    """Raised when a product asset should contain data but is empty."""


class PreprocessingNotFinished(Exception):
    """Raised when preprocessing tasks have not been fully executed."""


class AllMasked(Exception):
    """Raised when an array is fully masked."""


class NoSourceProducts(MapcheteNodataTile, ValueError):
    """Raised when no products are available."""


class CorruptedProductMetadata(Exception):
    """Raised when EOProduct cannot be parsed due to a metadata issue."""
