# Architecture

## Purpose
Documents the module layering, dependency direction, HTTP request path, error handling, and end-to-end data flow of the server.

## Responsibilities
- Describe each module's role and the strict import direction.
- Describe how a tool call travels from the MCP client to the Wunder API and back.
- Document the error/exception hierarchy and the single 401-retry behavior.

## Non-Responsibilities
- The token lifecycle internals — see [AUTHENTICATION.md](AUTHENTICATION.md).
- Per-tool parameters and field mapping — see [MCP-TOOLS.md](MCP-TOOLS.md).
- Naming/style rules — see [CONVENTIONS.md](CONVENTIONS.md).

## Overview

### Module layering
Single flat package `src/wunder_user_mcp/`, with a strict unidirectional dependency chain. Nothing imports "upward".

```
config.py  ->  auth.py  ->  client.py  ->  server.py
geo.py  ----------------------------------> server.py   (no internal imports)
```

- **`config.py`** — `Settings` (`@dataclass(frozen=True)`) plus `load_settings()`. Computes `auth_base` (`{base_url}/{tenant}/auth`) and `front_base` (`{base_url}/{tenant}/front`) as properties. Raises `ConfigError` on missing/invalid env.
- **`auth.py`** — `TokenManager` owns the access-token lifecycle; `_decode_jwt_exp()` reads the JWT `exp` without signature verification; `_safe_error_detail()` formats API error bodies. See [AUTHENTICATION.md](AUTHENTICATION.md).
- **`client.py`** — `WunderClient` wraps `/{tenant}/front` endpoints. `_request()` is the single authenticated dispatcher; `WunderApiError` carries `status_code` and `detail`.
- **`geo.py`** — stateless pure functions: `haversine_km()`, `extract_position()`, `attach_distance_and_sort()`. No internal imports, no state.
- **`server.py`** — `FastMCP` instance, the four `@mcp.tool()` functions, lazy singletons, and `main()`.

### Request path
`WunderClient._request(method, path, *, params, json)` is the only place authenticated HTTP happens:
1. Build the URL: `settings.front_base + path`.
2. Strip `None` query params via `_drop_none()`.
3. Loop up to 2 attempts:
   - `await tokens.get_access_token()` → set `Authorization: Bearer <token>`.
   - Issue the request via the shared `httpx.AsyncClient`.
   - On `401` and first attempt: `tokens.invalidate()` and retry once.
   - On status `>= 400`: raise `WunderApiError(status, detail)`.
   - Otherwise return the `httpx.Response`.
4. A second consecutive 401 raises `WunderApiError(401, …)`.

List endpoints (`list_vehicles`, `list_rentals`) pass the response JSON through `_as_list()`, which tolerates both bare lists and wrapped objects (keys `content`/`items`/`data`/`results`).

### Data flow (end to end)
```
MCP client (AI coding agent / MCP host)
  -> server.<tool>()            # validate args, map snake_case -> camelCase
    -> TokenManager.get_access_token()   # cached or refreshed
    -> WunderClient.<method>()  # authenticated httpx call to /{tenant}/front/...
      -> Wunder v2 API
  <- (vehicles only, when located) geo.attach_distance_and_sort()
  <- dict result to the caller
```
Singletons in `server.py`: `_require_settings()` builds `Settings` once (also called eagerly in `main()` to fail fast); `_get_client()` builds the shared `WunderClient` once, guarded by `_client_lock`, bound to the running event loop.

### Error / exception hierarchy
All derive from `RuntimeError`:
- `ConfigError` (`config.py`) — missing/invalid env at load time.
- `AuthError` (`auth.py`) — refresh-token exchange failed (network or non-2xx).
- `WunderApiError` (`client.py`) — API returned `>= 400` (or a transport error, raised as status `0`); exposes `status_code`/`detail`.
- `ValueError` — tool argument validation in `server.py`.

There is no global handler; FastMCP wraps exceptions at the transport layer. Error detail comes from `_safe_error_detail()`, which joins `errorCode | userMessage | message` from the JSON body (falling back to truncated text).

## Dependencies
- Internal: the chain above (`config` ← `auth` ← `client` ← `server`; `geo` ← `server`).
- External: `httpx` (transport), `mcp`/`FastMCP` (tool runtime).

## Design Decisions
- **Single `_request` gateway** centralizes auth, param cleaning, and retry so every endpoint method stays a one-liner.
- **Lazy, loop-bound singletons** ensure the `httpx.AsyncClient` is created inside the running event loop, not at import time.
- **Verbatim error propagation** (see [CONVENTIONS.md](CONVENTIONS.md)) keeps tenant-specific Wunder error codes/messages intact for the caller.

## Known Risks
- `client.py` imports the private `_safe_error_detail` from `auth.py` — reaching into another module's private API; a shared `_http`/utils module would be cleaner.
- Module-level mutable singletons (`_settings`, `_client`, `_client_lock`) make `server.py` non-reentrant and awkward to unit-test without module reload.
- The final `raise WunderApiError(401, _safe_error_detail(resp))` relies on `resp` from the loop body; safe because `range(2)` always runs, but static analyzers may flag possibly-unbound.

## Extension Guidelines
- New API calls: add an `async` method on `WunderClient` that delegates to `_request()`; do not call `httpx` directly elsewhere.
- New tools: add an `@mcp.tool()` function in `server.py`, validate inputs, call the client, return a `dict` (see [MCP-TOOLS.md](MCP-TOOLS.md)).
- Preserve the import direction — never import `server`/`client` from `config`/`auth`/`geo`.
