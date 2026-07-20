from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from products.integrations.auth import (
    SupplierCredentials,
)
from products.integrations.exceptions import (
    SupplierOperationNotSupportedError,
)
from products.integrations.http import (
    SupplierHTTPClient,
)

@dataclass
class SupplierOperationResult:
    """
    Standard response returned by supplier adapter operations.
    """

    success: bool
    operation: str
    message: str = ""
    data: Any = None
    external_reference: str = ""
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    @classmethod
    def succeeded(
        cls,
        operation,
        *,
        message="",
        data=None,
        external_reference="",
        metadata=None,
    ):
        return cls(
            success=True,
            operation=operation,
            message=message,
            data=data,
            external_reference=external_reference,
            metadata=metadata or {},
        )

    @classmethod
    def failed(
        cls,
        operation,
        *,
        message="",
        data=None,
        metadata=None,
    ):
        return cls(
            success=False,
            operation=operation,
            message=message,
            data=data,
            metadata=metadata or {},
        )


class BaseSupplierAdapter(ABC):
    """
    Base contract for all supplier integrations.

    Supplier-specific adapters override only the operations supported by
    that supplier. Unsupported operations raise a consistent exception.
    """

    supplier_slug = ""
    display_name = ""
    supports_api = False
    supports_csv = False
    supports_purchase_orders = False
    supports_tracking = False

    def __init__(self, supplier):
        self.supplier = supplier

        self.credentials = (
            SupplierCredentials.from_supplier(
                supplier,
                required=False,
            )
        )

        self.http = self.build_http_client()

    def test_connection(self):
        """
        Verify that the integration is usable.
        """

        return SupplierOperationResult.succeeded(
            "test_connection",
            message=(
                f"{self.supplier.name} adapter is available."
            ),
            metadata={
                "supplier_slug": self.supplier.slug,
                "api_enabled": self.supplier.api_enabled,
                "api_configured": (
                    self.credentials.is_configured
                ),
            },
        )

    def fetch_catalog(self, **kwargs):
        self._unsupported("fetch_catalog")

    def fetch_inventory(self, **kwargs):
        self._unsupported("fetch_inventory")

    def fetch_pricing(self, **kwargs):
        self._unsupported("fetch_pricing")

    def submit_purchase_order(
        self,
        purchase_order,
        **kwargs,
    ):
        self._unsupported(
            "submit_purchase_order"
        )

    def fetch_purchase_order_status(
        self,
        purchase_order,
        **kwargs,
    ):
        self._unsupported(
            "fetch_purchase_order_status"
        )

    def fetch_tracking(
        self,
        purchase_order,
        **kwargs,
    ):
        self._unsupported("fetch_tracking")

    def normalize_product(self, payload):
        """
        Convert supplier data to the common product dictionary expected by
        the marketplace import services.
        """

        self._unsupported("normalize_product")

    def _unsupported(self, operation):
        raise SupplierOperationNotSupportedError(
            (
                f"{self.__class__.__name__} does not support "
                f"the '{operation}' operation."
            )
        )
    
    def build_http_client(self):
        """
        Build the supplier HTTP client.

        Individual supplier adapters may override this method when they need
        custom authentication headers or retry settings.
        """

        headers = {}

        if self.credentials.api_key:
            headers.update(
                self.credentials.authorization_headers()
            )

        return SupplierHTTPClient(
            base_url=self.credentials.api_base_url,
            default_headers=headers,
        )