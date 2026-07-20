class SupplierIntegrationError(Exception):
    """
    Base exception for supplier integration failures.
    """


class SupplierAdapterNotFoundError(SupplierIntegrationError):
    """
    Raised when no adapter is registered for a supplier.
    """


class SupplierAuthenticationError(SupplierIntegrationError):
    """
    Raised when supplier credentials are missing or invalid.
    """


class SupplierConnectionError(SupplierIntegrationError):
    """
    Raised when the supplier integration cannot connect.
    """


class SupplierOperationNotSupportedError(
    SupplierIntegrationError
):
    """
    Raised when an adapter does not support an operation.
    """


class SupplierRequestError(SupplierIntegrationError):
    """
    Raised when a supplier request fails.
    """


class SupplierResponseError(SupplierIntegrationError):
    """
    Raised when a supplier returns malformed data.
    """