from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = (
        "django.db.models.BigAutoField"
    )

    name = "products"

    def ready(self):
        """
        Register built-in supplier synchronization operations after the
        Django application registry has loaded.
        """

        from products.integrations.registered_operations import (
            register_default_supplier_operations,
        )

        register_default_supplier_operations()