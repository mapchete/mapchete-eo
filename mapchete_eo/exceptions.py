"""Custom exceptions."""


class EmptyFootprintException(Exception):
    """Raised when footprint is empty."""


class EmptyProductException(Exception):
    """Raised when product is empty."""


class EmptySliceException(Exception):
    """Raised when slice is empty."""


class EmptyStackException(Exception):
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
