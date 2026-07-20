from products.integrations.exceptions import (
    SupplierAdapterNotFoundError,
)


_ADAPTER_REGISTRY = {}


def normalize_supplier_slug(value):
    return str(value or "").strip().lower()


def register_adapter(adapter_class):
    """
    Register an adapter class using its supplier_slug.
    """

    supplier_slug = normalize_supplier_slug(
        getattr(
            adapter_class,
            "supplier_slug",
            "",
        )
    )

    if not supplier_slug:
        raise ValueError(
            "Supplier adapters must define supplier_slug."
        )

    existing = _ADAPTER_REGISTRY.get(
        supplier_slug
    )

    if (
        existing is not None
        and existing is not adapter_class
    ):
        raise ValueError(
            (
                f"An adapter is already registered for "
                f"'{supplier_slug}'."
            )
        )

    _ADAPTER_REGISTRY[supplier_slug] = (
        adapter_class
    )

    return adapter_class


def unregister_adapter(supplier_slug):
    supplier_slug = normalize_supplier_slug(
        supplier_slug
    )

    return _ADAPTER_REGISTRY.pop(
        supplier_slug,
        None,
    )


def get_adapter_class(supplier_slug):
    supplier_slug = normalize_supplier_slug(
        supplier_slug
    )

    adapter_class = _ADAPTER_REGISTRY.get(
        supplier_slug
    )

    if adapter_class is None:
        raise SupplierAdapterNotFoundError(
            (
                "No supplier adapter is registered for "
                f"'{supplier_slug}'."
            )
        )

    return adapter_class


def get_supplier_adapter(supplier):
    """
    Return an initialized adapter for a Supplier model instance.
    """

    adapter_class = get_adapter_class(
        supplier.slug
    )

    return adapter_class(supplier)


def registered_adapters():
    return dict(_ADAPTER_REGISTRY)