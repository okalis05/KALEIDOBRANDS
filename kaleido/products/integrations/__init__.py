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
from products.integrations.orchestration import (
    SupplierSyncBatchAlreadyRunning,
    SupplierSyncBatchError,
    SupplierSyncJobDependencyError,
    SupplierSyncOrchestrator,
)
from products.integrations.sync_context import (
    SupplierSyncExecutionContext,
    SupplierSyncResult,
)
from products.integrations.sync_operations import (
    SupplierSyncOperation,
    SupplierSyncOperationError,
    SupplierSyncOperationNotRegistered,
    clear_sync_operations,
    get_sync_operation,
    register_sync_operation,
    registered_sync_operations,
    unregister_sync_operation,
)
from products.integrations.operation_dispatch import (
    OPERATION_METHOD_CANDIDATES,
    SupplierOperationCapabilityError,
    invoke_adapter_operation,
    normalize_operation_result,
    resolve_adapter_operation,
)
from products.integrations.registered_operations import (
    register_default_supplier_operations,
    sync_catalog_operation,
    sync_discontinued_operation,
    sync_images_operation,
    sync_inventory_operation,
    sync_pricing_operation,
)

# Import adapters so their registration decorators run.
from products.integrations import adapters  # noqa: F401


__all__ = [
    "SupplierSyncBatchAlreadyRunning",
    "SupplierSyncBatchError",
    "SupplierSyncExecutionContext",
    "SupplierSyncJobDependencyError",
    "SupplierSyncOperation",
    "SupplierSyncOperationError",
    "SupplierSyncOperationNotRegistered",
    "SupplierSyncOrchestrator",
    "SupplierSyncResult",
    "clear_sync_operations",
    "get_sync_operation",
    "register_sync_operation",
    "registered_sync_operations",
    "unregister_sync_operation",
    "OPERATION_METHOD_CANDIDATES",
    "SupplierOperationCapabilityError",
    "invoke_adapter_operation",
    "normalize_operation_result",
    "register_default_supplier_operations",
    "resolve_adapter_operation",
    "sync_catalog_operation",
    "sync_discontinued_operation",
    "sync_images_operation",
    "sync_inventory_operation",
    "sync_pricing_operation",
]