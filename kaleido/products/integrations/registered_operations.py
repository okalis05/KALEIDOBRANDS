from products.integrations.operation_dispatch import (
    invoke_adapter_operation,
)
from products.integrations.sync_operations import (
    get_sync_operation,
    register_sync_operation,
)


def _register_if_missing(
    name,
    handler,
    *,
    sequence,
    depends_on="",
    max_attempts=3,
):
    """
    Register an operation without overriding an explicitly registered
    application-specific handler.
    """

    if get_sync_operation(name):
        return

    register_sync_operation(
        name,
        handler,
        sequence=sequence,
        depends_on=depends_on,
        max_attempts=max_attempts,
    )


def sync_catalog_operation(
    context,
):
    return invoke_adapter_operation(
        adapter=context.adapter,
        operation="sync_catalog",
        context=context,
    )


def sync_inventory_operation(
    context,
):
    return invoke_adapter_operation(
        adapter=context.adapter,
        operation="sync_inventory",
        context=context,
    )


def sync_pricing_operation(
    context,
):
    return invoke_adapter_operation(
        adapter=context.adapter,
        operation="sync_pricing",
        context=context,
    )


def sync_images_operation(
    context,
):
    return invoke_adapter_operation(
        adapter=context.adapter,
        operation="sync_images",
        context=context,
    )


def sync_discontinued_operation(
    context,
):
    return invoke_adapter_operation(
        adapter=context.adapter,
        operation="sync_discontinued",
        context=context,
    )


def register_default_supplier_operations():
    """
    Register the standard supplier synchronization operation pipeline.

    Sequence:

    10 — catalog
    20 — pricing
    30 — inventory
    40 — images
    50 — discontinued products
    """

    _register_if_missing(
        "sync_catalog",
        sync_catalog_operation,
        sequence=10,
        max_attempts=3,
    )

    _register_if_missing(
        "sync_pricing",
        sync_pricing_operation,
        sequence=20,
        depends_on="sync_catalog",
        max_attempts=3,
    )

    _register_if_missing(
        "sync_inventory",
        sync_inventory_operation,
        sequence=30,
        depends_on="sync_catalog",
        max_attempts=3,
    )

    _register_if_missing(
        "sync_images",
        sync_images_operation,
        sequence=40,
        depends_on="sync_catalog",
        max_attempts=2,
    )

    _register_if_missing(
        "sync_discontinued",
        sync_discontinued_operation,
        sequence=50,
        depends_on="sync_catalog",
        max_attempts=2,
    )