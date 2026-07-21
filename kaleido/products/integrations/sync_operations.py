from dataclasses import dataclass
from threading import RLock


class SupplierSyncOperationError(Exception):
    """
    Raised when a supplier synchronization operation cannot be resolved
    or executed.
    """


class SupplierSyncOperationNotRegistered(
    SupplierSyncOperationError
):
    """
    Raised when no registered handler or adapter method exists for an
    operation.
    """


@dataclass(frozen=True)
class SupplierSyncOperation:
    """
    Registered supplier synchronization operation.
    """

    name: str
    handler: object
    sequence: int = 0
    depends_on: str = ""
    max_attempts: int = 3


_operation_registry = {}
_registry_lock = RLock()


def register_sync_operation(
    name,
    handler=None,
    *,
    sequence=0,
    depends_on="",
    max_attempts=3,
):
    """
    Register a callable supplier sync operation.

    May be used as a decorator or as a normal function.
    """

    normalized_name = str(
        name or ""
    ).strip()

    if not normalized_name:
        raise ValueError(
            "A supplier sync operation name is required."
        )

    def decorator(operation_handler):
        if not callable(operation_handler):
            raise TypeError(
                "Supplier sync operation handlers must be callable."
            )

        operation = SupplierSyncOperation(
            name=normalized_name,
            handler=operation_handler,
            sequence=max(
                int(sequence),
                0,
            ),
            depends_on=str(
                depends_on or ""
            ).strip(),
            max_attempts=max(
                int(max_attempts),
                1,
            ),
        )

        with _registry_lock:
            _operation_registry[
                normalized_name
            ] = operation

        return operation_handler

    if handler is not None:
        return decorator(handler)

    return decorator


def unregister_sync_operation(name):
    normalized_name = str(
        name or ""
    ).strip()

    with _registry_lock:
        return _operation_registry.pop(
            normalized_name,
            None,
        )


def get_sync_operation(name):
    normalized_name = str(
        name or ""
    ).strip()

    with _registry_lock:
        return _operation_registry.get(
            normalized_name
        )


def registered_sync_operations():
    with _registry_lock:
        return dict(_operation_registry)


def clear_sync_operations():
    """
    Clear the operation registry.

    Primarily intended for isolated tests.
    """

    with _registry_lock:
        _operation_registry.clear()