import json
import socket
import uuid
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from django.test import TestCase

from products.integrations.audit import (
    sanitize_headers,
    sanitize_metadata,
)
from products.integrations.context import (
    supplier_correlation_context,
)
from products.integrations.exceptions import (
    SupplierAuthenticationError,
    SupplierServerError,
    SupplierTimeoutError,
)
from products.integrations.http import (
    SupplierHTTPClient,
)
from products.models import (
    Supplier,
    SupplierIntegrationAuditLog,
)


def build_response(
    *,
    status=200,
    body=b"",
    headers=None,
):
    response = MagicMock()
    response.status = status
    response.getcode.return_value = status
    response.read.return_value = body
    response.headers = headers or {}

    return response


def build_http_error(
    *,
    status,
    body=b"",
    headers=None,
    url="https://supplier.example.com/test",
):
    return HTTPError(
        url=url,
        code=status,
        msg="Supplier error",
        hdrs=headers or {},
        fp=BytesIO(body),
    )


class SupplierAuditSanitizationTests(
    TestCase
):
    def test_sensitive_headers_are_redacted(
        self,
    ):
        sanitized = sanitize_headers(
            {
                "Authorization": (
                    "Bearer secret-token"
                ),
                "X-API-Key": (
                    "secret-api-key"
                ),
                "Accept": (
                    "application/json"
                ),
            }
        )

        self.assertEqual(
            sanitized["Authorization"],
            "[REDACTED]",
        )

        self.assertEqual(
            sanitized["X-API-Key"],
            "[REDACTED]",
        )

        self.assertEqual(
            sanitized["Accept"],
            "application/json",
        )

    def test_nested_secrets_are_redacted(
        self,
    ):
        sanitized = sanitize_metadata(
            {
                "credentials": {
                    "api_key": "secret",
                    "password": "password",
                },
                "page": 2,
            }
        )

        self.assertEqual(
            sanitized["credentials"][
                "api_key"
            ],
            "[REDACTED]",
        )

        self.assertEqual(
            sanitized["credentials"][
                "password"
            ],
            "[REDACTED]",
        )

        self.assertEqual(
            sanitized["page"],
            2,
        )


class SupplierHTTPAuditTests(TestCase):
    def setUp(self):
        self.supplier = (
            Supplier.objects.create(
                name="Audit Supplier",
                slug="audit-supplier",
                api_base_url=(
                    "https://supplier.example.com"
                ),
                api_enabled=True,
            )
        )

        self.sleep = MagicMock()

        self.client = SupplierHTTPClient(
            base_url=(
                "https://supplier.example.com"
            ),
            default_headers={
                "Authorization": (
                    "Bearer secret-token"
                ),
            },
            timeout=10,
            max_retries=2,
            backoff_factor=1,
            sleep_function=self.sleep,
            supplier=self.supplier,
            audit_enabled=True,
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_successful_request_creates_audit_log(
        self,
        mock_urlopen,
    ):
        mock_urlopen.return_value = (
            build_response(
                status=200,
                body=json.dumps(
                    {
                        "available": True,
                    }
                ).encode("utf-8"),
                headers={
                    "Content-Type": (
                        "application/json"
                    ),
                },
            )
        )

        response = self.client.get(
            "inventory",
            operation="fetch_inventory",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        log = (
            SupplierIntegrationAuditLog
            .objects.get()
        )

        self.assertEqual(
            log.supplier,
            self.supplier,
        )

        self.assertEqual(
            log.operation,
            "fetch_inventory",
        )

        self.assertEqual(
            log.method,
            "GET",
        )

        self.assertEqual(
            log.status,
            (
                SupplierIntegrationAuditLog
                .STATUS_SUCCEEDED
            ),
        )

        self.assertTrue(log.success)
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.attempt_count, 1)

        self.assertIsNotNone(
            log.completed_at
        )

        self.assertEqual(
            log.request_metadata[
                "headers"
            ]["Authorization"],
            "[REDACTED]",
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_retry_attempt_count_is_recorded(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = [
            build_http_error(status=503),
            build_response(
                status=200,
                body=b"{}",
                headers={
                    "Content-Type": (
                        "application/json"
                    ),
                },
            ),
        ]

        self.client.get(
            "inventory",
            operation="fetch_inventory",
        )

        log = (
            SupplierIntegrationAuditLog
            .objects.get()
        )

        self.assertTrue(log.success)
        self.assertEqual(
            log.attempt_count,
            2,
        )

        self.sleep.assert_called_once_with(1)

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_failed_server_request_is_audited(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = [
            build_http_error(status=500),
            build_http_error(status=500),
            build_http_error(status=500),
        ]

        with self.assertRaises(
            SupplierServerError
        ):
            self.client.get(
                "inventory",
                operation="fetch_inventory",
            )

        log = (
            SupplierIntegrationAuditLog
            .objects.get()
        )

        self.assertFalse(log.success)

        self.assertEqual(
            log.status,
            (
                SupplierIntegrationAuditLog
                .STATUS_FAILED
            ),
        )

        self.assertEqual(log.status_code, 500)
        self.assertEqual(log.attempt_count, 3)

        self.assertEqual(
            log.error_type,
            "SupplierServerError",
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_authentication_failure_is_audited_without_retry(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = (
            build_http_error(status=401)
        )

        with self.assertRaises(
            SupplierAuthenticationError
        ):
            self.client.get(
                "inventory",
                operation="fetch_inventory",
            )

        log = (
            SupplierIntegrationAuditLog
            .objects.get()
        )

        self.assertFalse(log.success)
        self.assertEqual(log.status_code, 401)
        self.assertEqual(log.attempt_count, 1)
        self.assertEqual(
            mock_urlopen.call_count,
            1,
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_timeout_failure_is_audited(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = (
            socket.timeout()
        )

        with self.assertRaises(
            SupplierTimeoutError
        ):
            self.client.get(
                "inventory",
                operation="fetch_inventory",
            )

        log = (
            SupplierIntegrationAuditLog
            .objects.get()
        )

        self.assertFalse(log.success)
        self.assertEqual(log.attempt_count, 3)

        self.assertEqual(
            log.error_type,
            "SupplierTimeoutError",
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_related_requests_share_correlation_id(
        self,
        mock_urlopen,
    ):
        mock_urlopen.return_value = (
            build_response(
                status=200,
                body=b"{}",
                headers={
                    "Content-Type": (
                        "application/json"
                    ),
                },
            )
        )

        expected_id = uuid.uuid4()

        with supplier_correlation_context(
            expected_id
        ):
            self.client.get(
                "catalog",
                operation="fetch_catalog",
            )

            self.client.get(
                "inventory",
                operation="fetch_inventory",
            )

        logs = list(
            SupplierIntegrationAuditLog
            .objects.order_by("id")
        )

        self.assertEqual(len(logs), 2)

        self.assertEqual(
            logs[0].correlation_id,
            expected_id,
        )

        self.assertEqual(
            logs[1].correlation_id,
            expected_id,
        )

        self.assertNotEqual(
            logs[0].request_id,
            logs[1].request_id,
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_explicit_correlation_id_is_supported(
        self,
        mock_urlopen,
    ):
        mock_urlopen.return_value = (
            build_response(
                status=200,
                body=b"{}",
                headers={
                    "Content-Type": (
                        "application/json"
                    ),
                },
            )
        )

        correlation_id = uuid.uuid4()

        self.client.get(
            "catalog",
            operation="fetch_catalog",
            correlation_id=correlation_id,
        )

        log = (
            SupplierIntegrationAuditLog
            .objects.get()
        )

        self.assertEqual(
            log.correlation_id,
            correlation_id,
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_auditing_can_be_disabled(
        self,
        mock_urlopen,
    ):
        client = SupplierHTTPClient(
            base_url=(
                "https://supplier.example.com"
            ),
            supplier=self.supplier,
            audit_enabled=False,
        )

        mock_urlopen.return_value = (
            build_response(
                status=200,
                body=b"{}",
                headers={
                    "Content-Type": (
                        "application/json"
                    ),
                },
            )
        )

        client.get("catalog")

        self.assertFalse(
            SupplierIntegrationAuditLog
            .objects.exists()
        )