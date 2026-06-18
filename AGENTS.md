# wunder-user-mcp
> An MCP server that exposes the Wunder Mobility v2 end-user (User) API as tools, so an AI coding agent or MCP client can browse vehicles and create/operate rentals on behalf of one signed-in end user.

> **Editing this guide:** `AGENTS.md` is the single source of truth for project context, read by all AI coding agents and humans. Keep it concise — put detail in `docs/` and link it. When you change code that alters documented behavior, update the matching `docs/` file in the **same PR** (CodeRabbit enforces this — see [docs/README.md](docs/README.md)).

## Quick Reference
- **Install**: `uv sync` (installs main + dev deps)
- **Run (local)**: `uv run wunder-user-mcp` (needs `WUNDER_REFRESH_TOKEN` + `WUNDER_TENANT`)
- **Run (from git)**: `uvx --from git+https://github.com/slettmayer/wunder-user-mcp wunder-user-mcp`
- **Test**: `uv run pytest`
- **Lint**: `uv run ruff check`

## Where to Find Things
| I need to... | Read |
|--------------|------|
| Understand the architecture | [ARCHITECTURE.md](docs/tech/ARCHITECTURE.md) |
| Know the tech stack | [TECH-STACK.md](docs/tech/TECH-STACK.md) |
| Write code that fits conventions | [CONVENTIONS.md](docs/tech/CONVENTIONS.md) |
| Understand the MCP tools (the product surface) | [MCP-TOOLS.md](docs/tech/MCP-TOOLS.md) |
| Understand token/auth handling | [AUTHENTICATION.md](docs/tech/AUTHENTICATION.md) |
| Write or run tests | [TESTING.md](docs/tech/TESTING.md) |
| Understand the business domain | [docs/domain/](docs/domain/README.md) |

## Architecture Overview
Layered async Python package (`src/` layout, single flat package `wunder_user_mcp`) with a strict, unidirectional dependency chain:

```
config.py  ->  auth.py  ->  client.py  ->  server.py
geo.py  ----------------------------------> server.py   (stateless helper, no internal imports)
```

- `config.py` — `Settings` (frozen dataclass) loaded fail-fast from `WUNDER_*` env vars.
- `auth.py` — `TokenManager`: exchanges the refresh token for short-lived JWT access tokens, refreshes proactively and on 401.
- `client.py` — `WunderClient`: thin `httpx.AsyncClient` wrapper over `/{tenant}/front` endpoints; single 401-retry; surfaces API errors verbatim.
- `geo.py` — pure haversine distance + best-effort vehicle position extraction and sorting.
- `server.py` — `FastMCP` instance, the 4 `@mcp.tool()` functions, and `main()`.

Data flow: MCP client calls a tool → `server` validates args → `TokenManager` ensures a valid bearer token → `WunderClient` calls the Wunder v2 API → vehicle results optionally pass through `geo` for distance sorting → result returned to the caller.

## Tech Stack
- **Language**: Python 3.10+ (`from __future__ import annotations` everywhere).
- **Framework**: MCP (`mcp` SDK, `FastMCP`), served over **stdio**.
- **HTTP**: `httpx` async client.
- **Build/packaging**: `uv` + `hatchling`; distributed via `uvx` from the git source.
- **Tooling**: `pytest` + `pytest-asyncio`, `ruff` (line length 100).
- No database, no persistence — the server is a stateless proxy to the Wunder v2 API.

## Core Conventions
- One module = one responsibility; respect the `config → auth → client → server` import direction.
- Async everywhere for I/O; all public client/tool methods are `async`.
- Full type hints; `dict[str, Any]` for opaque API JSON payloads.
- Validate tool arguments with plain `raise ValueError(...)` before calling the client.
- Surface API errors verbatim: `_safe_error_detail` extracts `errorCode | userMessage | message`; relay these, do not invent messages.
- Inbound `snake_case` tool params map to the API's `camelCase` body/query keys in `server.py`/`client.py`.
- See [CONVENTIONS.md](docs/tech/CONVENTIONS.md) for detail.

## Business Domain
Shared / micro-mobility vehicle rental. Core entities: **vehicle**, **rental** (states `RESERVATION` and `ACTIVE`), **tenant**, **branch**, and an implicit single **user**. The four tools cover vehicle discovery and the full rental lifecycle against one Wunder Mobility tenant. See [docs/domain/OVERVIEW.md](docs/domain/OVERVIEW.md) and [GLOSSARY.md](docs/domain/GLOSSARY.md).

**High-impact operations:** `create_rental` (especially `start_rental_state=ACTIVE`) and `rental_command` with `END` trigger real vehicle commands, pricing, payment authorization/capture, deposits, and invoices. Confirm intent before issuing them.

## Structural Risks
- `client.py` imports the private `_safe_error_detail` from `auth.py` — a cross-module reach into a private helper; candidate for a shared `_http`/utils module.
- `server.py` uses module-level mutable singletons (`_settings`, `_client`, `_client_lock`), making the module non-reentrant and hard to test without reload.
- No integration tests for `WunderClient`/`TokenManager`/tools — only offline unit tests for `geo` and JWT-exp parsing. `httpx.MockTransport`/`respx` would close the gap.
- No CI/CD configured (no `.github/`); lint/test are manual.
- Ruff runs only the default rule set (only `line-length`/`target-version` configured).

## Detailed Guides
- [Technical Context](docs/tech/README.md) — tech stack, architecture, conventions, MCP tools, authentication, testing
- [Domain Context](docs/domain/README.md) — domain overview, entities, rental lifecycle, terminology
