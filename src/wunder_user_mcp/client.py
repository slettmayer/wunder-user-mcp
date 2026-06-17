"""HTTP client for the Wunder end-user (front) API."""

from __future__ import annotations

from typing import Any

import httpx

from wunder_user_mcp.auth import TokenManager, _safe_error_detail
from wunder_user_mcp.config import Settings


class WunderApiError(RuntimeError):
    """Raised when a Wunder API call returns an error response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Wunder API error (HTTP {status_code}): {detail}")


class WunderClient:
    """Thin async wrapper around the /{tenant}/front endpoints."""

    def __init__(self, settings: Settings, http: httpx.AsyncClient, tokens: TokenManager) -> None:
        self._settings = settings
        self._http = http
        self._tokens = tokens

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> httpx.Response:
        """Issue an authenticated request, refreshing + retrying once on 401."""
        url = f"{self._settings.front_base}{path}"
        clean_params = _drop_none(params) if params else None

        for attempt in range(2):
            token = await self._tokens.get_access_token()
            headers = {"Authorization": f"Bearer {token}"}
            try:
                resp = await self._http.request(
                    method, url, params=clean_params, json=json, headers=headers
                )
            except httpx.HTTPError as exc:
                raise WunderApiError(0, f"request failed: {exc}") from exc

            if resp.status_code == 401 and attempt == 0:
                self._tokens.invalidate()
                continue
            if resp.status_code >= 400:
                raise WunderApiError(resp.status_code, _safe_error_detail(resp))
            return resp

        # Exhausted the retry after a second 401.
        raise WunderApiError(401, _safe_error_detail(resp))

    async def list_vehicles(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        resp = await self._request("GET", "/vehicles", params=params)
        return _as_list(resp.json())

    async def list_rentals(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        resp = await self._request("GET", "/rentals", params=params)
        return _as_list(resp.json())

    async def rental_operation(self, rental_id: int, body: dict[str, Any]) -> dict[str, Any]:
        resp = await self._request("POST", f"/rentals/{rental_id}/operation", json=body)
        return resp.json()

    async def create_rental(self, body: dict[str, Any]) -> dict[str, Any]:
        resp = await self._request("POST", "/rentals", json=body)
        return resp.json()


def _drop_none(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


def _as_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    # Some list endpoints may wrap results; be tolerant.
    if isinstance(payload, dict):
        for key in ("content", "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []
