import json
import socket
from email.message import Message
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from django.test import SimpleTestCase

from products.integrations.exceptions import (
    SupplierAuthenticationError,
    SupplierConnectionError,
    SupplierRateLimitError,
    SupplierRequestError,
    SupplierResponseError,
    SupplierServerError,
    SupplierTimeoutError,
)
from products.integrations.http import (
    SupplierHTTPClient,
    SupplierHTTPResponse,
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
    error = HTTPError(
        url=url,
        code=status,
        msg="Supplier error",
        hdrs=headers or {},
        fp=BytesIO(body),
    )

    return error


class SupplierHTTPClientTests(SimpleTestCase):
    def setUp(self):
        self.sleep = MagicMock()

        self.client = SupplierHTTPClient(
            base_url=(
                "https://supplier.example.com/api"
            ),
            timeout=15,
            max_retries=2,
            backoff_factor=1,
            max_backoff=10,
            sleep_function=self.sleep,
            audit_enabled=False,
        )

    def test_build_url_joins_base_url_and_path(
        self,
    ):
        url = self.client.build_url(
            "/products"
        )

        self.assertEqual(
            url,
            (
                "https://supplier.example.com/"
                "api/products"
            ),
        )

    def test_build_url_encodes_query_parameters(
        self,
    ):
        url = self.client.build_url(
            "products",
            params={
                "page": 2,
                "active": True,
                "tag": ["pens", "bags"],
                "ignored": None,
            },
        )

        self.assertIn(
            "page=2",
            url,
        )

        self.assertIn(
            "active=True",
            url,
        )

        self.assertIn(
            "tag=pens",
            url,
        )

        self.assertIn(
            "tag=bags",
            url,
        )

        self.assertNotIn(
            "ignored",
            url,
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_successful_json_response_is_normalized(
        self,
        mock_urlopen,
    ):
        mock_urlopen.return_value = build_response(
            status=200,
            body=json.dumps(
                {
                    "products": [
                        {
                            "id": "P-100",
                        }
                    ]
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": (
                    "application/json"
                )
            },
        )

        response = self.client.get(
            "products"
        )

        self.assertIsInstance(
            response,
            SupplierHTTPResponse,
        )

        self.assertTrue(
            response.successful
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.data["products"][0]["id"],
            "P-100",
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_post_serializes_json_body(
        self,
        mock_urlopen,
    ):
        mock_urlopen.return_value = build_response(
            status=201,
            body=b'{"created": true}',
            headers={
                "Content-Type": (
                    "application/json"
                )
            },
        )

        response = self.client.post(
            "purchase-orders",
            json_data={
                "po_number": "KB-PO-100",
            },
        )

        request = (
            mock_urlopen.call_args.args[0]
        )

        self.assertEqual(
            request.method,
            "POST",
        )

        self.assertEqual(
            json.loads(
                request.data.decode("utf-8")
            ),
            {
                "po_number": "KB-PO-100",
            },
        )

        self.assertEqual(
            response.status_code,
            201,
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_text_response_is_preserved(
        self,
        mock_urlopen,
    ):
        mock_urlopen.return_value = build_response(
            status=200,
            body=b"Supplier available",
            headers={
                "Content-Type": "text/plain"
            },
        )

        response = self.client.get(
            "health"
        )

        self.assertEqual(
            response.data,
            "Supplier available",
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_invalid_json_raises_response_error(
        self,
        mock_urlopen,
    ):
        mock_urlopen.return_value = build_response(
            status=200,
            body=b'{"invalid":',
            headers={
                "Content-Type": (
                    "application/json"
                )
            },
        )

        with self.assertRaises(
            SupplierResponseError
        ):
            self.client.get("products")

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_server_error_is_retried(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = [
            build_http_error(
                status=503
            ),
            build_response(
                status=200,
                body=b'{"available": true}',
                headers={
                    "Content-Type": (
                        "application/json"
                    )
                },
            ),
        ]

        response = self.client.get(
            "health"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            mock_urlopen.call_count,
            2,
        )

        self.sleep.assert_called_once_with(
            1
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_retry_uses_exponential_backoff(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = [
            build_http_error(
                status=500
            ),
            build_http_error(
                status=502
            ),
            build_response(
                status=200,
                body=b"{}",
                headers={
                    "Content-Type": (
                        "application/json"
                    )
                },
            ),
        ]

        self.client.get("products")

        self.assertEqual(
            self.sleep.call_args_list[0].args,
            (1,),
        )

        self.assertEqual(
            self.sleep.call_args_list[1].args,
            (2,),
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_retry_after_header_is_respected(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = [
            build_http_error(
                status=429,
                headers={
                    "Retry-After": "7"
                },
            ),
            build_response(
                status=200,
                body=b"{}",
                headers={
                    "Content-Type": (
                        "application/json"
                    )
                },
            ),
        ]

        self.client.get("products")

        self.sleep.assert_called_once_with(
            7
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_rate_limit_error_after_retries(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = [
            build_http_error(
                status=429
            ),
            build_http_error(
                status=429
            ),
            build_http_error(
                status=429
            ),
        ]

        with self.assertRaises(
            SupplierRateLimitError
        ) as context:
            self.client.get("products")

        self.assertEqual(
            context.exception.status_code,
            429,
        )

        self.assertTrue(
            context.exception.retryable
        )

        self.assertEqual(
            mock_urlopen.call_count,
            3,
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_server_error_after_retries(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = [
            build_http_error(
                status=500
            ),
            build_http_error(
                status=500
            ),
            build_http_error(
                status=500
            ),
        ]

        with self.assertRaises(
            SupplierServerError
        ) as context:
            self.client.get("products")

        self.assertEqual(
            context.exception.status_code,
            500,
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_non_retryable_request_error_is_immediate(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = (
            build_http_error(
                status=400,
                body=b'{"error": "invalid"}',
            )
        )

        with self.assertRaises(
            SupplierRequestError
        ) as context:
            self.client.get("products")

        self.assertEqual(
            context.exception.status_code,
            400,
        )

        self.assertFalse(
            context.exception.retryable
        )

        self.assertEqual(
            mock_urlopen.call_count,
            1,
        )

        self.sleep.assert_not_called()

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_authentication_error_is_not_retried(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = (
            build_http_error(
                status=401
            )
        )

        with self.assertRaises(
            SupplierAuthenticationError
        ):
            self.client.get("products")

        self.assertEqual(
            mock_urlopen.call_count,
            1,
        )

        self.sleep.assert_not_called()

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_timeout_is_retried(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = [
            socket.timeout(),
            build_response(
                status=200,
                body=b"{}",
                headers={
                    "Content-Type": (
                        "application/json"
                    )
                },
            ),
        ]

        response = self.client.get(
            "products"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.sleep.assert_called_once_with(
            1
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_timeout_error_after_retry_limit(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = (
            socket.timeout()
        )

        with self.assertRaises(
            SupplierTimeoutError
        ):
            self.client.get("products")

        self.assertEqual(
            mock_urlopen.call_count,
            3,
        )

    @patch(
        "products.integrations.http.urlopen"
    )
    def test_connection_error_after_retry_limit(
        self,
        mock_urlopen,
    ):
        mock_urlopen.side_effect = URLError(
            "connection refused"
        )

        with self.assertRaises(
            SupplierConnectionError
        ):
            self.client.get("products")

        self.assertEqual(
            mock_urlopen.call_count,
            3,
        )