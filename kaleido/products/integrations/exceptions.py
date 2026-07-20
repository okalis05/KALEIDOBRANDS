class SupplierIntegrationError(Exception):
    """
    Base exception for supplier integration failures.
    """


class SupplierAdapterNotFoundError(
    SupplierIntegrationError
):
    """
    Raised when no adapter is registered for a supplier.
    """


class SupplierAuthenticationError(
    SupplierIntegrationError
):
    """
    Raised when supplier credentials are missing or invalid.
    """


class SupplierConnectionError(
    SupplierIntegrationError
):
    """
    Raised when a supplier integration cannot connect.
    """


class SupplierOperationNotSupportedError(
    SupplierIntegrationError
):
    """
    Raised when an adapter does not support an operation.
    """


class SupplierRequestError(
    SupplierIntegrationError
):
    """
    Raised when a supplier request fails.
    """

    def __init__(
        self,
        message,
        *,
        status_code=None,
        response_body=None,
        retryable=False,
    ):
        super().__init__(message)

        self.status_code = status_code
        self.response_body = response_body
        self.retryable = retryable


class SupplierResponseError(
    SupplierIntegrationError
):
    """
    Raised when a supplier returns malformed data.
    """


class SupplierTimeoutError(
    SupplierConnectionError
):
    """
    Raised when a supplier request times out.
    """


class SupplierRateLimitError(
    SupplierRequestError
):
    """
    Raised when a supplier API rate limit is exhausted.
    """


class SupplierServerError(
    SupplierRequestError
):
    """
    Raised when a supplier API returns a server error.
    """