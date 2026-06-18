# Conventions

## Purpose
Documents the naming, code-style, typing, validation, and error-handling conventions that new code must follow.

## Responsibilities
- Record naming and style rules consistently applied across the package.
- Record the input-validation and error-surfacing patterns.
- Record the snake_case ↔ camelCase mapping rule at the API boundary.

## Non-Responsibilities
- Module layering — see [ARCHITECTURE.md](ARCHITECTURE.md).
- Tool definitions — see [MCP-TOOLS.md](MCP-TOOLS.md).
- Test conventions — see [TESTING.md](TESTING.md).

## Overview

### Naming
- **Files/modules**: `snake_case.py`, named by responsibility (`config`, `auth`, `client`, `geo`, `server`). No `*Service`/`*Repository` suffixes.
- **Classes**: `PascalCase`, role-descriptive — `Settings`, `TokenManager`, `WunderClient`, and the exceptions `ConfigError`, `AuthError`, `WunderApiError`.
- **Functions/methods**: `snake_case` verbs. Public async methods are action verbs (`get_access_token`, `list_vehicles`, `rental_operation`). Private helpers carry a leading underscore (`_request`, `_refresh`, `_decode_jwt_exp`, `_safe_error_detail`, `_drop_none`, `_as_list`, `_coord`, `_from_geojson`).
- **MCP tool functions**: the function name IS the tool name the client sees — `get_vehicles`, `get_active_rental`, `rental_command`, `create_rental`.
- **Constants**: `UPPER_SNAKE_CASE` at module level (`DEFAULT_BASE_URL`, `_EXPIRY_MARGIN_S`, `_EARTH_RADIUS_KM`); private ones prefixed `_`.
- **Env vars**: `WUNDER_` prefix, `UPPER_SNAKE_CASE`.

### Code style
- 4-space indentation, double quotes, trailing commas in multi-line literals/signatures.
- `from __future__ import annotations` at the top of every production module (except `__init__.py`/`__main__.py`).
- Max line length 100 (ruff). Imports ordered stdlib → third-party → `wunder_user_mcp.*` (ruff-enforced).
- Comprehensive type hints on all signatures, returns, and instance attributes. Use `dict[str, Any]` for opaque API JSON; `Any` only where the payload is genuinely opaque.

### Configuration
- Read from `os.environ` directly — no dotenv loader. `Settings` is a `frozen=True` dataclass.
- Fail fast: `load_settings()` raises `ConfigError` listing every missing required var (`WUNDER_REFRESH_TOKEN`, `WUNDER_TENANT`). Numeric vars are parsed via `_get_float`/`_get_int`, which raise `ConfigError` on non-numeric input.
- Defaults live as module constants; empty/whitespace env values fall back to the default.

Required and optional env vars:

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `WUNDER_REFRESH_TOKEN` | yes | — | Long-lived end-user refresh token |
| `WUNDER_TENANT` | yes | — | Tenant short-code in the URL path |
| `WUNDER_BASE_URL` | no | `https://go.api.gourban.services/v1` | API gateway base URL |
| `WUNDER_BRANCH_ID` | no | — | Default branch id for vehicle/rental calls |
| `WUNDER_DEFAULT_RADIUS_MI` | no | `5` | Default search radius (miles) for `get_vehicles` |
| `WUNDER_HTTP_TIMEOUT` | no | `30` | Per-request timeout (seconds) |

### Input validation
- Tools validate arguments themselves with plain `raise ValueError(...)` before touching the client. Examples: `get_vehicles` requires both `latitude`/`longitude` or neither; `create_rental` requires exactly one of `vehicle_id`/`vehicle_code`.
- `start_rental_state` is a `Literal["RESERVATION", "ACTIVE"]` and re-checked at runtime.

### snake_case ↔ camelCase boundary
- Tool parameters are `snake_case` (Pythonic, what the LLM sees). The request body/query keys sent to the Wunder API are `camelCase`. The mapping is explicit in `server.py` (e.g. `branch_id` → `branchId`, `start_rental_state` → `startRentalState`, `vehicle_code` → `vehicleCode`) and in `client.py` params.

### Error handling
- API errors surface verbatim. `_safe_error_detail()` joins `errorCode | userMessage | message` from the response body; that detail becomes the exception message and is meant to be relayed to the user, not reinterpreted.
- Network failures are caught (`httpx.HTTPError`) and re-raised as the domain error (`AuthError`, or `WunderApiError(0, …)`).
- Only one retry exists: the 401 re-auth in `WunderClient._request`. No transient-network retry.

## Dependencies
- Style is enforced by `ruff`; types are hints only (no mypy gate configured).

## Design Decisions
- **No dotenv** keeps the dependency surface minimal and makes configuration explicit at the process boundary.
- **Self-validating tools** mean argument errors are caught before any network call, producing clear `ValueError`s to the client.

## Known Risks
- Ruff runs the default rule set only — style beyond `E`/`F` (e.g. `bugbear`, `pyupgrade`, import-order strictness) is not enforced.

## Extension Guidelines
- New tool params: keep them `snake_case`, validate early with `ValueError`, and map explicitly to the API's `camelCase` key.
- New env vars: add a default constant, parse in `load_settings()`, document the var in this table and the root `README.md`.
- Do not swallow API errors — let `WunderApiError`/`AuthError` propagate so the caller sees the Wunder `errorCode`/`userMessage`.
