import json
import socket
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from products.integrations.exceptions import (
    SupplierAuthenticationError,
    SupplierConnectionError,
    SupplierRateLimitError,
    SupplierRequestError,
    SupplierResponseError,
    SupplierServerError,
    SupplierTimeoutError,
)
from products.integrations.audit import (
    SupplierIntegrationAuditService,
    sanitize_headers,
)
from products.integrations.context import (
    get_correlation_id,
)

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 1.0
DEFAULT_MAX_BACKOFF_SECONDS = 30.0

RETRYABLE_STATUS_CODES = {
    429,
    500,
    502,
    503,
    504,
}


@dataclass
class SupplierHTTPResponse:
    """
    Normalized response returned by SupplierHTTPClient.
    """

    status_code: int
    data: Any = None
    headers: Dict[str, str] = field(
        default_factory=dict
    )
    raw_body: str = ""
    url: str = ""

    @property
    def successful(self):
        return 200 <= self.status_code < 300


class SupplierHTTPClient:
    """
    Reusable HTTP client for supplier integrations.

    Features:
    - JSON request and response handling
    - query-string encoding
    - configurable timeouts
    - exponential retry backoff
    - Retry-After support
    - normalized supplier exceptions
    """

    def __init__(
        self,
        *,
        base_url="",
        default_headers=None,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        max_retries=DEFAULT_MAX_RETRIES,
        backoff_factor=DEFAULT_BACKOFF_FACTOR,
        max_backoff=DEFAULT_MAX_BACKOFF_SECONDS,
        sleep_function=None,
        supplier=None,
        audit_enabled=True,
    ):
        self.base_url = str(
            base_url or ""
        ).rstrip("/")

        self.default_headers = dict(
            default_headers or {}
        )

        self.timeout = timeout

        self.max_retries = max(
            int(max_retries),
            0,
        )

        self.backoff_factor = max(
            float(backoff_factor),
            0.0,
        )

        self.max_backoff = max(
            float(max_backoff),
            0.0,
        )

        self.sleep_function = (
            sleep_function or time.sleep
        )

        self.supplier = supplier
        self.audit_enabled = bool(
            audit_enabled
        )

    def build_url(
        self,
        path="",
        *,
        params=None,
    ):
        path = str(path or "").strip()

        if path.startswith(
            ("http://", "https://")
        ):
            url = path

        elif self.base_url:
            if path:
                url = (
                    f"{self.base_url}/"
                    f"{path.lstrip('/')}"
                )
            else:
                url = self.base_url

        else:
            url = path

        if not url:
            raise ValueError(
                "A supplier request URL is required."
            )

        if params:
            filtered_params = {
                key: value
                for key, value in params.items()
                if value is not None
            }

            query_string = urlencode(
                filtered_params,
                doseq=True,
            )

            if query_string:
                separator = (
                    "&"
                    if "?" in url
                    else "?"
                )

                url = (
                    f"{url}{separator}"
                    f"{query_string}"
                )

        return url

    def get(
        self,
        path="",
        *,
        params=None,
        headers=None,
        timeout=None,
        operation=None,
        correlation_id=None,
    ):
        return self.request(
            "GET",
            path,
            params=params,
            headers=headers,
            timeout=timeout,
            operation=operation,
            correlation_id=correlation_id,
        )

    def post(
        self,
        path="",
        *,
        params=None,
        json_data=None,
        headers=None,
        timeout=None,
        operation=None,
        correlation_id=None,
    ):
        return self.request(
            "POST",
            path,
            params=params,
            json_data=json_data,
            headers=headers,
            timeout=timeout,
            operation=operation,
            correlation_id=correlation_id,
        )

    def put(
        self,
        path="",
        *,
        params=None,
        json_data=None,
        headers=None,
        timeout=None,
        operation=None,
        correlation_id=None,
    ):
        return self.request(
            "PUT",
            path,
            params=params,
            json_data=json_data,
            headers=headers,
            timeout=timeout,
            operation=operation,
            correlation_id=correlation_id,
        )

    def patch(
        self,
        path="",
        *,
        params=None,
        json_data=None,
        headers=None,
        timeout=None,
        operation=None,
        correlation_id=None,
    ):
        return self.request(
            "PATCH",
            path,
            params=params,
            json_data=json_data,
            headers=headers,
            timeout=timeout,
            operation=operation,
            correlation_id=correlation_id,
        )

    def delete(
        self,
        path="",
        *,
        params=None,
        headers=None,
        timeout=None,
        operation=None,
        correlation_id=None,
    ):
        return self.request(
            "DELETE",
            path,
            params=params,
            headers=headers,
            timeout=timeout,
            operation=operation,
            correlation_id=correlation_id,
        )
    def request(
        self,
        method,
        path="",
        *,
        params=None,
        json_data=None,
        headers=None,
        timeout=None,
        operation=None,
        correlation_id=None,
    ):
        method = str(
            method or "GET"
        ).upper()

        url = self.build_url(
            path,
            params=params,
        )

        request_headers = {
            "Accept": "application/json",
            **self.default_headers,
            **dict(headers or {}),
        }

        request_body = None

        if json_data is not None:
            request_headers.setdefault(
                "Content-Type",
                "application/json",
            )

            request_body = json.dumps(
                json_data
            ).encode("utf-8")

        request_timeout = (
            self.timeout
            if timeout is None
            else timeout
        )

        operation = (
            operation
            or self._default_operation(
                method,
                path,
            )
        )

        correlation_id = (
            correlation_id
            or get_correlation_id()
        )

        audit_session = None

        if self.audit_enabled:
            audit_session = (
                SupplierIntegrationAuditService
                .start(
                    supplier=self.supplier,
                    operation=operation,
                    method=method,
                    url=url,
                    correlation_id=correlation_id,
                    request_metadata={
                        "headers": sanitize_headers(
                            request_headers
                        ),
                        "has_json_body": (
                            json_data is not None
                        ),
                        "query_parameter_names": sorted(
                            str(key)
                            for key in (
                                params or {}
                            ).keys()
                        ),
                        "timeout_seconds": (
                            request_timeout
                        ),
                    },
                )
            )

        attempt = 0

        while True:
            try:
                request = Request(
                    url=url,
                    data=request_body,
                    headers=request_headers,
                    method=method,
                )

                response = urlopen(
                    request,
                    timeout=request_timeout,
                )

                normalized_response = (
                    self._build_response(
                        response,
                        url=url,
                    )
                )

                if audit_session:
                    audit_session.complete(
                        status_code=(
                            normalized_response
                            .status_code
                        ),
                        attempt_count=attempt + 1,
                        response_metadata={
                            "headers": sanitize_headers(
                                normalized_response
                                .headers
                            ),
                            "response_type": type(
                                normalized_response.data
                            ).__name__,
                        },
                    )

                return normalized_response

            except HTTPError as error:
                supplier_error = (
                    self._translate_http_error(
                        error,
                        url=url,
                    )
                )

                if (
                    getattr(
                        supplier_error,
                        "retryable",
                        False,
                    )
                    and attempt < self.max_retries
                ):
                    delay = self._retry_delay(
                        attempt,
                        headers=dict(
                            error.headers or {}
                        ),
                    )

                    self.sleep_function(delay)
                    attempt += 1
                    continue

                if audit_session:
                    audit_session.fail(
                        supplier_error,
                        status_code=getattr(
                            supplier_error,
                            "status_code",
                            error.code,
                        ),
                        attempt_count=attempt + 1,
                        response_metadata={
                            "retryable": getattr(
                                supplier_error,
                                "retryable",
                                False,
                            ),
                        },
                    )

                raise supplier_error from error

            except (
                socket.timeout,
                TimeoutError,
            ) as error:
                if attempt < self.max_retries:
                    delay = self._retry_delay(
                        attempt
                    )

                    self.sleep_function(delay)
                    attempt += 1
                    continue

                supplier_error = (
                    SupplierTimeoutError(
                        (
                            "Supplier request timed out "
                            f"after {attempt + 1} "
                            f"attempt(s): {url}"
                        )
                    )
                )

                if audit_session:
                    audit_session.fail(
                        supplier_error,
                        attempt_count=attempt + 1,
                    )

                raise supplier_error from error

            except URLError as error:
                reason = getattr(
                    error,
                    "reason",
                    error,
                )

                if isinstance(
                    reason,
                    socket.timeout,
                ):
                    if attempt < self.max_retries:
                        delay = self._retry_delay(
                            attempt
                        )

                        self.sleep_function(delay)
                        attempt += 1
                        continue

                    supplier_error = (
                        SupplierTimeoutError(
                            (
                                "Supplier request timed "
                                "out after "
                                f"{attempt + 1} "
                                "attempt(s): "
                                f"{url}"
                            )
                        )
                    )

                else:
                    if attempt < self.max_retries:
                        delay = self._retry_delay(
                            attempt
                        )

                        self.sleep_function(delay)
                        attempt += 1
                        continue

                    supplier_error = (
                        SupplierConnectionError(
                            (
                                "Unable to connect to "
                                "supplier endpoint: "
                                f"{url}. "
                                f"Reason: {reason}"
                            )
                        )
                    )

                if audit_session:
                    audit_session.fail(
                        supplier_error,
                        attempt_count=attempt + 1,
                    )

                raise supplier_error from error

            except SupplierResponseError as error:
                if audit_session:
                    audit_session.fail(
                        error,
                        attempt_count=attempt + 1,
                    )

                raise


    def _default_operation(
        self,
        method,
        path,
    ):
        normalized_path = str(
            path or ""
        ).strip("/")

        if not normalized_path:
            normalized_path = "root"

        normalized_path = (
            normalized_path
            .replace("/", ".")
            .replace("?", ".")
        )

        return (
            f"{str(method).lower()}."
            f"{normalized_path}"
        )[:100]

    def _build_response(
        self,
        response,
        *,
        url,
    ):
        status_code = getattr(
            response,
            "status",
            None,
        )

        if status_code is None:
            status_code = response.getcode()

        raw_bytes = response.read()
        raw_body = raw_bytes.decode(
            "utf-8",
            errors="replace",
        )

        headers = dict(
            response.headers or {}
        )

        data = self._parse_response_body(
            raw_body,
            headers=headers,
        )

        return SupplierHTTPResponse(
            status_code=status_code,
            data=data,
            headers=headers,
            raw_body=raw_body,
            url=url,
        )

    def _parse_response_body(
        self,
        raw_body,
        *,
        headers=None,
    ):
        if not raw_body:
            return None

        headers = headers or {}

        content_type = str(
            headers.get(
                "Content-Type",
                headers.get(
                    "content-type",
                    "",
                ),
            )
        ).lower()

        should_parse_json = (
            "application/json" in content_type
            or raw_body.lstrip().startswith(
                ("{", "[")
            )
        )

        if not should_parse_json:
            return raw_body

        try:
            return json.loads(raw_body)

        except json.JSONDecodeError as error:
            raise SupplierResponseError(
                "Supplier returned invalid JSON."
            ) from error

    def _translate_http_error(
        self,
        error,
        *,
        url,
    ):
        status_code = error.code

        raw_body = ""

        try:
            raw_body = error.read().decode(
                "utf-8",
                errors="replace",
            )
        except Exception:
            raw_body = ""

        message = (
            f"Supplier request failed with HTTP "
            f"{status_code}: {url}"
        )

        common_kwargs = {
            "status_code": status_code,
            "response_body": raw_body,
            "retryable": (
                status_code
                in RETRYABLE_STATUS_CODES
            ),
        }

        if status_code in {401, 403}:
            return SupplierAuthenticationError(
                message
            )

        if status_code == 429:
            return SupplierRateLimitError(
                message,
                **common_kwargs,
            )

        if 500 <= status_code <= 599:
            return SupplierServerError(
                message,
                **common_kwargs,
            )

        return SupplierRequestError(
            message,
            **common_kwargs,
        )

    def _retry_delay(
        self,
        attempt,
        *,
        headers=None,
    ):
        headers = headers or {}

        retry_after = (
            headers.get("Retry-After")
            or headers.get("retry-after")
        )

        if retry_after is not None:
            try:
                delay = float(retry_after)

                return min(
                    max(delay, 0.0),
                    self.max_backoff,
                )

            except (
                TypeError,
                ValueError,
            ):
                pass

        delay = (
            self.backoff_factor
            * (2 ** attempt)
        )

        return min(
            delay,
            self.max_backoff,
        )
