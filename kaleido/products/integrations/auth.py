import os
from dataclasses import dataclass
from typing import Optional

from products.integrations.exceptions import (
    SupplierAuthenticationError,
)


@dataclass(frozen=True)
class SupplierCredentials:
    """
    Runtime credentials for one supplier integration.

    Secret values are read from environment variables and are never
    persisted directly on the Supplier model.
    """

    api_base_url: str = ""
    api_key: str = ""
    api_key_name: str = ""

    @classmethod
    def from_supplier(
        cls,
        supplier,
        *,
        required=False,
    ):
        api_key_name = (
            supplier.api_key_name or ""
        ).strip()

        api_key = ""

        if api_key_name:
            api_key = os.getenv(
                api_key_name,
                "",
            ).strip()

        if required and not api_key:
            raise SupplierAuthenticationError(
                (
                    f"Missing API credential for "
                    f"{supplier.name}. Expected environment "
                    f"variable: {api_key_name or 'not configured'}."
                )
            )

        return cls(
            api_base_url=(
                supplier.api_base_url or ""
            ).rstrip("/"),
            api_key=api_key,
            api_key_name=api_key_name,
        )

    @property
    def is_configured(self):
        return bool(
            self.api_base_url
            and self.api_key
        )

    def authorization_headers(
        self,
        *,
        header_name="Authorization",
        prefix="Bearer",
    ):
        if not self.api_key:
            raise SupplierAuthenticationError(
                "Supplier API key is not configured."
            )

        value = self.api_key

        if prefix:
            value = f"{prefix} {self.api_key}"

        return {
            header_name: value,
        }