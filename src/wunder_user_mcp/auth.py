"""Access-token lifecycle: exchange a refresh token and cache the access token.

The Wunder access token is a JWT with a default 5h lifetime. We decode its `exp`
claim (without verifying the signature — we only need the expiry) and refresh
proactively shortly before it lapses, or on demand after a 401.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import time

import httpx

from wunder_user_mcp.config import Settings

# Refresh this many seconds before the token's `exp` to avoid edge-of-expiry races.
_EXPIRY_MARGIN_S = 60
# Fallback lifetime if a token has no decodable `exp` claim (defensive).
_FALLBACK_LIFETIME_S = 4 * 60 * 60


class AuthError(RuntimeError):
    """Raised when the refresh-token exchange fails."""


def _decode_jwt_exp(token: str) -> float | None:
    """Return the `exp` (unix seconds) from a JWT payload, or None if absent."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload_b64 = parts[1]
    # JWT uses base64url without padding; pad to a multiple of 4 before decoding.
    padding = "=" * (-len(payload_b64) % 4)
    try:
        payload_raw = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_raw)
    except (binascii.Error, ValueError):
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        return float(exp)
    return None


class TokenManager:
    """Maintains a valid access token, refreshing from the configured refresh token."""

    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http
        self._refresh_token = settings.refresh_token
        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    def _is_valid(self) -> bool:
        return bool(self._access_token) and time.time() < (self._expires_at - _EXPIRY_MARGIN_S)

    async def get_access_token(self) -> str:
        """Return a valid access token, refreshing if needed (single-flight)."""
        if self._is_valid():
            return self._access_token  # type: ignore[return-value]
        async with self._lock:
            # Re-check: another coroutine may have refreshed while we waited.
            if self._is_valid():
                return self._access_token  # type: ignore[return-value]
            await self._refresh()
            return self._access_token  # type: ignore[return-value]

    def invalidate(self) -> None:
        """Drop the cached access token, forcing a refresh on next use (e.g. after 401)."""
        self._access_token = None
        self._expires_at = 0.0

    async def _refresh(self) -> None:
        url = f"{self._settings.auth_base}/refresh-token"
        try:
            resp = await self._http.post(url, json={"refreshToken": self._refresh_token})
        except httpx.HTTPError as exc:
            raise AuthError(f"Could not reach the Wunder auth endpoint: {exc}") from exc

        if resp.status_code >= 400:
            detail = _safe_error_detail(resp)
            raise AuthError(
                f"Refresh-token exchange failed (HTTP {resp.status_code}): {detail}"
            )

        data = resp.json()
        access_token = data.get("accessToken")
        if not access_token:
            raise AuthError("Auth response did not contain an accessToken.")

        # Rotate the refresh token in memory if the backend issued a new one.
        new_refresh = data.get("refreshToken")
        if new_refresh:
            self._refresh_token = new_refresh

        self._access_token = access_token
        exp = _decode_jwt_exp(access_token)
        self._expires_at = exp if exp is not None else time.time() + _FALLBACK_LIFETIME_S


def _safe_error_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300]
    if isinstance(body, dict):
        parts = [str(body[k]) for k in ("errorCode", "userMessage", "message") if body.get(k)]
        if parts:
            return " | ".join(parts)
    return str(body)[:300]
