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



# Import adapters so their registration decorators run.
from products.integrations import adapters  # noqa: F401


__all__ = [
    "BaseSupplierAdapter",
    "SupplierOperationResult",
    "SupplierHTTPClient",
    "SupplierHTTPResponse",
    "get_adapter_class",
    "get_supplier_adapter",
    "register_adapter",
    "registered_adapters",
]