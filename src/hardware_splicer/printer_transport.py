"""HTTP transport for configured fabrication printers.

Endpoints and credentials are operator configuration, never mission/agent
input. This module intentionally performs no discovery and stores no secrets.
The same transport supports OctoPrint and Moonraker multipart uploads and JSON
control requests.
"""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlsplit

import httpx

from .fabrication_operator import FabricationValidationError


class HttpxPrinterTransport:
    def __init__(
        self,
        base_url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ):
        if not isinstance(base_url, str):
            raise FabricationValidationError("printer base_url must be a string")
        cleaned = base_url.strip().rstrip("/")
        parsed = urlsplit(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise FabricationValidationError("printer base_url must be an absolute http(s) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise FabricationValidationError("printer base_url must not embed credentials, query or fragment")
        if type(timeout_seconds) not in {int, float} or not 0.1 <= float(timeout_seconds) <= 120.0:
            raise FabricationValidationError("printer timeout must be between 0.1 and 120 seconds")

        self.base_url = cleaned
        self.headers = dict(headers or {})
        self.timeout_seconds = float(timeout_seconds)
        self._client = client or httpx.Client(timeout=self.timeout_seconds)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "HttpxPrinterTransport":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _url(self, path: str) -> str:
        if not isinstance(path, str) or not path.startswith("/"):
            raise FabricationValidationError("printer request path must start with '/'")
        # Adapters own request paths. A configured base URL is never replaced by
        # an absolute path supplied by a model.
        return f"{self.base_url}{path}"

    @staticmethod
    def _json_response(response: httpx.Response) -> Mapping[str, Any]:
        response.raise_for_status()
        if not response.content:
            return {}
        value = response.json()
        if not isinstance(value, Mapping):
            raise FabricationValidationError("printer returned a non-object JSON response")
        return dict(value)

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        response = self._client.request(
            method,
            self._url(path),
            headers=self.headers,
            json=dict(json_body) if json_body is not None else None,
            timeout=self.timeout_seconds,
        )
        return self._json_response(response)

    def upload(
        self,
        path: str,
        *,
        filename: str,
        data: bytes,
        fields: Mapping[str, str],
    ) -> Mapping[str, Any]:
        response = self._client.post(
            self._url(path),
            headers=self.headers,
            data=dict(fields),
            files={"file": (filename, data, "application/octet-stream")},
            timeout=self.timeout_seconds,
        )
        return self._json_response(response)
