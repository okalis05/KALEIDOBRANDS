from products.integrations.base import (
    BaseSupplierAdapter,
    SupplierOperationResult,
)
from products.integrations.registry import (
    get_adapter_class,
    get_supplier_adapter,
    register_adapter,
    registered_adapters,
)
from products.integrations.http import (
    SupplierHTTPClient,
    SupplierHTTPResponse,
)
from products.integrations.audit import (
    SupplierIntegrationAuditService,
)
from products.integrations.context import (
    get_correlation_id,
    supplier_correlation_context,
)



# Import adapters so their registration decorators run.
from products.integrations import adapters  # noqa: F401


__all__ = [
    "BaseSupplierAdapter",
    "SupplierOperationResult",
    "SupplierHTTPClient",
    "SupplierHTTPResponse",
    "SupplierIntegrationAuditService",
    "get_correlation_id",
    "supplier_correlation_context",
    "get_adapter_class",
    "get_supplier_adapter",
    "register_adapter",
    "registered_adapters",
]