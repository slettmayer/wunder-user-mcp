# Tech Stack

## Purpose
Documents the languages, framework, build tooling, runtime libraries, and distribution mechanism of the project.

## Responsibilities
- Enumerate the languages, framework, and libraries actually in use.
- Record build/packaging and how the server is run and distributed.
- Record the developer toolchain (tests, lint).

## Non-Responsibilities
- Module layering and data flow — see [ARCHITECTURE.md](ARCHITECTURE.md).
- Coding style and naming — see [CONVENTIONS.md](CONVENTIONS.md).
- The tool surface — see [MCP-TOOLS.md](MCP-TOOLS.md).

## Overview

### Language
- Python `>=3.10` (`requires-python` in `pyproject.toml`).
- Every production module begins with `from __future__ import annotations`, enabling PEP 604 `X | Y` unions on 3.10.

### Framework
- **MCP** via the `mcp` SDK (`>=1.2.0`). The server is built on `FastMCP` (`mcp.server.fastmcp.FastMCP`), instantiated in `src/wunder_user_mcp/server.py`.
- Tools are plain `async` functions decorated with `@mcp.tool()`; their docstrings and type hints become the tool schema the client sees.
- Transport is **stdio** (`mcp.run()` in `main()`).

### HTTP
- `httpx` (`>=0.27`) `AsyncClient` for all upstream calls. A single client instance is shared across the process (built once in `server._get_client()`), with a configurable timeout (`WUNDER_HTTP_TIMEOUT`, default 30s).

### Data layer
- None. The server holds no database and no persistent state; it is a stateless proxy to the Wunder Mobility v2 API. The only in-memory state is the cached access token in `TokenManager`.

### Build & packaging
- **uv** for dependency resolution and running (`uv.lock` checked in).
- **hatchling** build backend; wheel packages `src/wunder_user_mcp` (`[tool.hatch.build.targets.wheel]`).
- Console script entry point: `wunder-user-mcp = "wunder_user_mcp.server:main"`. Module entry: `python -m wunder_user_mcp` via `__main__.py`.

### Distribution & run
```bash
# from the published git source (no clone, no PyPI):
uvx --from git+https://github.com/slettmayer/wunder-user-mcp wunder-user-mcp
# pin a ref:
uvx --from git+https://github.com/slettmayer/wunder-user-mcp@main wunder-user-mcp
# moving refs: add --refresh to bust the uvx build cache
# local dev:
uv run wunder-user-mcp        # editable
uvx --from . wunder-user-mcp  # build from cwd
```
`WUNDER_REFRESH_TOKEN` and `WUNDER_TENANT` must be set in the environment in all cases (see [CONVENTIONS.md](CONVENTIONS.md) and the root `README.md` for the full env table).

### Toolchain
- **pytest** (`>=8`) + **pytest-asyncio** (`>=0.23`, `asyncio_mode = "auto"`), `testpaths = ["tests"]`.
- **ruff** (`>=0.6`), `line-length = 100`, `target-version = "py310"`.
- Dependency groups: main = `mcp`, `httpx`; dev = `pytest`, `pytest-asyncio`, `ruff`.

## Dependencies
- External runtime: `mcp`, `httpx`.
- External dev: `pytest`, `pytest-asyncio`, `ruff`.
- Upstream service: the Wunder Mobility v2 API (`https://go.api.gourban.services/v1`; staging `go-staging.…`). See [docs/domain/OVERVIEW.md](../domain/OVERVIEW.md).

## Design Decisions
- **uvx-from-git distribution** avoids a PyPI publish while still giving consumers a one-line install; `--refresh` is the documented escape hatch for moving refs.
- **src layout** keeps the importable package isolated from repo-root tooling files.
- **No dotenv loader** — configuration is read directly from `os.environ`, keeping the dependency surface minimal (see [CONVENTIONS.md](CONVENTIONS.md)).

## Known Risks
- No CI/CD pipeline (`.github/` absent); lint and tests are run manually.
- Ruff uses only the default rule set; no `select`/`ignore` tuning beyond `line-length`/`target-version`.

## Extension Guidelines
- Add runtime deps under `[project] dependencies` and dev deps under `[dependency-groups] dev`; run `uv sync` to refresh `uv.lock`.
- Keep new modules inside `src/wunder_user_mcp/`; the wheel only packages that path.
- Preserve `from __future__ import annotations` at the top of new modules for consistent 3.10 union syntax.
