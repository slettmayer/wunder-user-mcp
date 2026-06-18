# Authentication

## Purpose
Documents how the server authenticates to the Wunder v2 API: exchanging a refresh token for short-lived access tokens, caching them, refreshing proactively and on 401, and rotating the refresh token.

## Responsibilities
- Describe `TokenManager` and its token lifecycle.
- Describe JWT `exp` decoding and the proactive-refresh margin.
- Describe single-flight refresh and the invalidate-on-401 path.

## Non-Responsibilities
- How tokens are attached to requests / the 401 retry loop — see [ARCHITECTURE.md](ARCHITECTURE.md).
- Where the refresh token comes from (sign-in) — see the root `README.md` and [docs/domain/OVERVIEW.md](../domain/OVERVIEW.md).

## Overview

`auth.py` owns the access-token lifecycle. Tool callers never see tokens.

### TokenManager
Constructed as `TokenManager(settings, http)` and held by `WunderClient`. State: the in-memory `_refresh_token` (seeded from `settings.refresh_token`), the cached `_access_token`, its `_expires_at`, and an `asyncio.Lock`.

- `get_access_token()` — returns a valid token, refreshing only if needed. Uses double-checked locking: it checks `_is_valid()`, acquires the lock, re-checks (another coroutine may have refreshed), then `_refresh()`. This is the **single-flight** guarantee — concurrent tool calls trigger at most one refresh.
- `_is_valid()` — true when an access token exists and `time.time() < _expires_at - _EXPIRY_MARGIN_S`. The margin (`_EXPIRY_MARGIN_S = 60`) forces a proactive refresh ~60s before expiry to avoid edge-of-expiry races.
- `invalidate()` — clears the cached token and `_expires_at`, forcing a refresh on next use. Called by `WunderClient._request` after a 401.

### Refresh exchange
`_refresh()` POSTs `{"refreshToken": <token>}` to `{settings.auth_base}/refresh-token` (i.e. `{base_url}/{tenant}/auth/refresh-token`):
- Transport failure (`httpx.HTTPError`) → `AuthError`.
- Status `>= 400` → `AuthError` with detail from `_safe_error_detail`.
- Missing `accessToken` in the body → `AuthError`.
- If the response includes a new `refreshToken`, it **rotates** `_refresh_token` in memory (the next refresh uses the new one). Rotation is in-memory only — the env var is not rewritten; a process restart reverts to the configured token.
- The new access token's expiry comes from `_decode_jwt_exp(access_token)`, falling back to `time.time() + _FALLBACK_LIFETIME_S` (`4h`) if the `exp` cannot be decoded.

### JWT exp decoding
`_decode_jwt_exp(token)` splits the JWT into 3 parts, base64url-decodes the payload (padding it to a multiple of 4), JSON-parses it, and returns the `exp` claim as a float. It does **not** verify the signature — only the expiry is needed. Returns `None` on any structural/parse failure or a missing/non-numeric `exp`.

## Dependencies
- `httpx.AsyncClient` (shared instance) for the refresh POST.
- `Settings.auth_base` for the endpoint URL.
- `_safe_error_detail` (also used by `client.py`) for error formatting.

## Design Decisions
- **Signature-free JWT decode**: the server is a client of the token, not its verifier; it only needs `exp` to schedule refreshes. The upstream API enforces the signature.
- **60s proactive margin + 4h fallback**: avoids handing out a token that expires mid-flight, and stays functional even if a token's `exp` is unparseable.
- **Single-flight via double-checked lock**: prevents a thundering herd of refresh calls when many tool invocations arrive while the token is expired.

## Known Risks
- Refresh-token rotation is in-memory only; a long-lived process uses the latest rotated token, while a restart falls back to the env-configured one. This is safe: the Wunder API does **not** invalidate the prior refresh token on rotation, so the env-configured token keeps working across restarts.
- `_safe_error_detail` is imported from `auth.py` into `client.py` (a private cross-module import) — see [ARCHITECTURE.md](ARCHITECTURE.md).

## Extension Guidelines
- Keep all token logic inside `TokenManager`; do not read or cache tokens elsewhere.
- If signature verification is ever required, add it as a separate concern — `_decode_jwt_exp` must stay expiry-only.
- Preserve the lock + double-check pattern when changing refresh logic to keep the single-flight guarantee.
