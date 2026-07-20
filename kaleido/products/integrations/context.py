import uuid
from contextlib import contextmanager
from contextvars import ContextVar


_current_correlation_id = ContextVar(
    "supplier_integration_correlation_id",
    default=None,
)


def normalize_uuid(value):
    if value is None:
        return None

    if isinstance(value, uuid.UUID):
        return value

    return uuid.UUID(str(value))


def get_correlation_id():
    """
    Return the active supplier integration correlation ID.

    A new UUID is generated when no correlation context is active.
    """

    current = _current_correlation_id.get()

    if current is not None:
        return current

    return uuid.uuid4()


@contextmanager
def supplier_correlation_context(
    correlation_id=None,
):
    """
    Group multiple supplier operations under one correlation ID.
    """

    correlation_id = (
        normalize_uuid(correlation_id)
        if correlation_id
        else uuid.uuid4()
    )

    token = _current_correlation_id.set(
        correlation_id
    )

    try:
        yield correlation_id
    finally:
        _current_correlation_id.reset(token)