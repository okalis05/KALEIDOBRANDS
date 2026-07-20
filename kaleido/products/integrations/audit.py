import time
from dataclasses import dataclass

from django.utils import timezone

from products.integrations.context import (
    get_correlation_id,
    normalize_uuid,
)
from products.models import (
    SupplierIntegrationAuditLog,
)


SENSITIVE_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "apikey",
    "cookie",
    "set-cookie",
}


SENSITIVE_METADATA_NAMES = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "client_secret",
}


def sanitize_headers(headers):
    """
    Redact sensitive HTTP header values before persistence.
    """

    sanitized = {}

    for key, value in dict(headers or {}).items():
        key_string = str(key)

        if key_string.lower() in SENSITIVE_HEADER_NAMES:
            sanitized[key_string] = "[REDACTED]"
        else:
            sanitized[key_string] = str(value)

    return sanitized


def sanitize_metadata(value):
    """
    Recursively redact common secret-bearing metadata keys.
    """

    if isinstance(value, dict):
        sanitized = {}

        for key, item in value.items():
            key_string = str(key)

            normalized_key = (
                key_string
                .lower()
                .replace("-", "_")
            )

            if normalized_key in SENSITIVE_METADATA_NAMES:
                sanitized[key_string] = "[REDACTED]"
            else:
                sanitized[key_string] = sanitize_metadata(
                    item
                )

        return sanitized

    if isinstance(value, (list, tuple)):
        return [
            sanitize_metadata(item)
            for item in value
        ]

    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    return str(value)


@dataclass
class SupplierAuditSession:
    """
    Runtime wrapper around one supplier integration audit record.
    """

    log: SupplierIntegrationAuditLog
    started_timer: float

    @property
    def request_id(self):
        return self.log.request_id

    @property
    def correlation_id(self):
        return self.log.correlation_id

    def _duration_ms(self):
        return max(
            int(
                (
                    time.monotonic()
                    - self.started_timer
                )
                * 1000
            ),
            0,
        )

    def complete(
        self,
        *,
        status_code=None,
        attempt_count=1,
        response_metadata=None,
    ):
        self.log.status = (
            SupplierIntegrationAuditLog
            .STATUS_SUCCEEDED
        )

        self.log.success = True
        self.log.status_code = status_code
        self.log.attempt_count = max(
            int(attempt_count),
            1,
        )
        self.log.duration_ms = self._duration_ms()

        self.log.response_metadata = sanitize_metadata(
            response_metadata or {}
        )

        self.log.error_type = ""
        self.log.error_message = ""
        self.log.completed_at = timezone.now()

        self.log.save(
            update_fields=[
                "status",
                "success",
                "status_code",
                "attempt_count",
                "duration_ms",
                "response_metadata",
                "error_type",
                "error_message",
                "completed_at",
            ]
        )

        return self.log

    def fail(
        self,
        error,
        *,
        status_code=None,
        attempt_count=1,
        response_metadata=None,
    ):
        self.log.status = (
            SupplierIntegrationAuditLog
            .STATUS_FAILED
        )

        self.log.success = False
        self.log.status_code = status_code
        self.log.attempt_count = max(
            int(attempt_count),
            1,
        )
        self.log.duration_ms = self._duration_ms()

        self.log.response_metadata = sanitize_metadata(
            response_metadata or {}
        )

        self.log.error_type = (
            error.__class__.__name__
        )

        self.log.error_message = str(error)[:4000]
        self.log.completed_at = timezone.now()

        self.log.save(
            update_fields=[
                "status",
                "success",
                "status_code",
                "attempt_count",
                "duration_ms",
                "response_metadata",
                "error_type",
                "error_message",
                "completed_at",
            ]
        )

        return self.log


class SupplierIntegrationAuditService:
    """
    Create persistent supplier request audit sessions.
    """

    @staticmethod
    def start(
        *,
        supplier=None,
        operation="",
        method="",
        url="",
        correlation_id=None,
        request_metadata=None,
    ):
        correlation_id = (
            normalize_uuid(correlation_id)
            if correlation_id
            else get_correlation_id()
        )

        log = (
            SupplierIntegrationAuditLog
            .objects.create(
                supplier=supplier,
                correlation_id=correlation_id,
                operation=str(
                    operation or ""
                )[:100],
                method=str(
                    method or ""
                ).upper()[:10],
                url=str(url or ""),
                status=(
                    SupplierIntegrationAuditLog
                    .STATUS_PENDING
                ),
                success=False,
                request_metadata=(
                    sanitize_metadata(
                        request_metadata or {}
                    )
                ),
            )
        )

        return SupplierAuditSession(
            log=log,
            started_timer=time.monotonic(),
        )