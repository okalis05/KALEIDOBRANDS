import inspect

from products.integrations.sync_context import (
    SupplierSyncResult,
)
from products.integrations.sync_operations import (
    SupplierSyncOperationNotRegistered,
)


class SupplierOperationCapabilityError(
    SupplierSyncOperationNotRegistered
):
    """
    Raised when a supplier adapter does not implement a capability
    required by a registered synchronization operation.
    """


OPERATION_METHOD_CANDIDATES = {
    "sync_catalog": (
        "sync_catalog",
        "fetch_catalog",
        "import_catalog",
        "list_products",
        "get_products",
        "fetch_products",
    ),
    "sync_inventory": (
        "sync_inventory",
        "fetch_inventory",
        "get_inventory",
        "list_inventory",
        "fetch_inventory_levels",
    ),
    "sync_pricing": (
        "sync_pricing",
        "fetch_pricing",
        "get_pricing",
        "list_prices",
        "fetch_prices",
    ),
    "sync_images": (
        "sync_images",
        "fetch_images",
        "get_images",
        "list_images",
        "fetch_product_images",
    ),
    "sync_discontinued": (
        "sync_discontinued",
        "fetch_discontinued",
        "get_discontinued",
        "list_discontinued",
        "fetch_discontinued_products",
    ),
}


def resolve_adapter_operation(
    adapter,
    operation,
):
    """
    Resolve the first supported adapter method for an operation.
    """

    operation = str(
        operation or ""
    ).strip()

    method_names = (
        OPERATION_METHOD_CANDIDATES.get(
            operation,
            (operation,),
        )
    )

    for method_name in method_names:
        handler = getattr(
            adapter,
            method_name,
            None,
        )

        if callable(handler):
            return handler

    adapter_name = (
        adapter.__class__.__name__
    )

    raise SupplierOperationCapabilityError(
        (
            f"{adapter_name} does not implement the "
            f"'{operation}' capability. Expected one "
            f"of these methods: "
            f"{', '.join(method_names)}."
        )
    )


def invoke_adapter_operation(
    *,
    adapter,
    operation,
    context,
):
    """
    Invoke an adapter operation using only arguments accepted by the
    resolved adapter method.
    """

    handler = resolve_adapter_operation(
        adapter,
        operation,
    )

    checkpoint = (
        context.checkpoint_data()
    )

    available_arguments = {
        "context": context,
        "sync_context": context,
        "job": getattr(
            context,
            "job",
            None,
        ),
        "supplier": getattr(
            context,
            "supplier",
            None,
        ),
        "checkpoint": checkpoint,
        "correlation_id": getattr(
            context,
            "correlation_id",
            "",
        ),
        "file_path": _batch_file_path(
            context
        ),
    }
    signature = inspect.signature(
        handler
    )

    args = []
    kwargs = {}

    for parameter_name, parameter in (
        signature.parameters.items()
    ):
        if parameter.kind == (
            inspect.Parameter.VAR_POSITIONAL
        ):
            continue

        if parameter.kind == (
            inspect.Parameter.VAR_KEYWORD
        ):
            continue

        if (
            parameter_name
            in available_arguments
        ):
            value = available_arguments[
                parameter_name
            ]

            if parameter.kind == (
                inspect.Parameter
                .POSITIONAL_ONLY
            ):
                args.append(value)

            else:
                kwargs[
                    parameter_name
                ] = value

            continue

        if (
            parameter.default
            is inspect.Parameter.empty
        ):
            raise SupplierOperationCapabilityError(
                (
                    f"Adapter method "
                    f"'{handler.__name__}' requires "
                    f"unsupported argument "
                    f"'{parameter_name}'."
                )
            )

    raw_result = handler(
        *args,
        **kwargs,
    )

    return normalize_operation_result(
        raw_result
    )


def normalize_operation_result(
    raw_result,
):
    """
    Convert adapter return values into SupplierSyncResult.
    """

    if raw_result is None:
        return SupplierSyncResult()

    if isinstance(
        raw_result,
        SupplierSyncResult,
    ):
        return raw_result

    if isinstance(raw_result, bool):
        count = 1 if raw_result else 0

        return SupplierSyncResult(
            records_processed=count,
            records_succeeded=count,
            records_failed=0 if raw_result else 1,
        )

    if isinstance(raw_result, int):
        count = max(
            int(raw_result),
            0,
        )

        return SupplierSyncResult(
            records_processed=count,
            records_succeeded=count,
        )

    if isinstance(raw_result, dict):
        return SupplierSyncResult(
            records_processed=_integer_value(
                raw_result,
                "records_processed",
                "processed",
                "total",
                "count",
            ),
            records_succeeded=_integer_value(
                raw_result,
                "records_succeeded",
                "succeeded",
                "successful",
                "created",
                "updated",
            ),
            records_failed=_integer_value(
                raw_result,
                "records_failed",
                "failed",
                "errors",
            ),
            checkpoint=dict(
                raw_result.get(
                    "checkpoint",
                    {},
                )
                or {}
            ),
            metadata=dict(
                raw_result.get(
                    "metadata",
                    {},
                )
                or {}
            ),
        )

    if isinstance(
        raw_result,
        (list, tuple, set),
    ):
        count = len(raw_result)

        return SupplierSyncResult(
            records_processed=count,
            records_succeeded=count,
            metadata={
                "result_type": (
                    raw_result
                    .__class__
                    .__name__
                ),
            },
        )

    processed = getattr(
        raw_result,
        "records_processed",
        getattr(
            raw_result,
            "processed",
            0,
        ),
    )

    succeeded = getattr(
        raw_result,
        "records_succeeded",
        getattr(
            raw_result,
            "succeeded",
            processed,
        ),
    )

    failed = getattr(
        raw_result,
        "records_failed",
        getattr(
            raw_result,
            "failed",
            0,
        ),
    )

    checkpoint = getattr(
        raw_result,
        "checkpoint",
        {},
    )

    metadata = getattr(
        raw_result,
        "metadata",
        {},
    )

    return SupplierSyncResult(
        records_processed=max(
            int(processed or 0),
            0,
        ),
        records_succeeded=max(
            int(succeeded or 0),
            0,
        ),
        records_failed=max(
            int(failed or 0),
            0,
        ),
        checkpoint=dict(
            checkpoint or {}
        ),
        metadata=dict(
            metadata or {}
        ),
    )


def _integer_value(
    payload,
    *keys,
):
    for key in keys:
        value = payload.get(key)

        if value is not None:
            try:
                return max(
                    int(value),
                    0,
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

    return 0


def _batch_file_path(
    context,
):
    if context is None:
        return None

    job = getattr(
        context,
        "job",
        None,
    )

    batch = getattr(
        job,
        "batch",
        None,
    )

    metadata = getattr(
        batch,
        "metadata",
        None,
    ) or {}

    return metadata.get(
        "file_path"
    )