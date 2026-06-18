# Testing

## Purpose
Documents the test framework, what is and is not covered, test conventions, and the developer commands.

## Responsibilities
- Record the test stack and scope (offline unit tests only).
- Record test file/function naming and structure.
- Record the dev/lint/test commands.

## Non-Responsibilities
- Production module behavior — see [ARCHITECTURE.md](ARCHITECTURE.md) and [AUTHENTICATION.md](AUTHENTICATION.md).
- Code style rules — see [CONVENTIONS.md](CONVENTIONS.md).

## Overview

### Stack
- `pytest` (`>=8`) with `pytest-asyncio` (`>=0.23`), `asyncio_mode = "auto"`, `testpaths = ["tests"]` (all in `pyproject.toml`).

### Scope
Tests are **offline unit tests for pure functions only** — no network, no mocks:
- `tests/test_auth.py` — `_decode_jwt_exp` (reads `exp`; handles a missing `exp`). Builds real, syntactically valid JWTs via a local `_make_jwt()` helper.
- `tests/test_geo.py` — `haversine_km`, `extract_position` (across field-layout variants), and `attach_distance_and_sort` (ascending order, unknown-position vehicles sort last). Uses real city coordinates (Hamburg/Berlin/Vienna) as self-documenting fixtures.

Not covered: `WunderClient`, `TokenManager` (beyond exp decoding), the MCP tools, and `config.load_settings`. This is an intentional boundary — the README describes the suite as "offline unit tests (geo + JWT exp parsing)".

### Conventions
- File naming: `test_<module>.py`.
- Function naming: `test_<function>_<scenario>` (e.g. `test_extract_position_variants`, `test_attach_distance_and_sort_orders_ascending_and_pushes_unknown_last`).
- Plain module-level functions, arrange–assert, no test classes.
- All current tests are synchronous because the tested functions are synchronous; `asyncio_mode = "auto"` is already set so `async def test_…` functions run without a decorator when async coverage is added.

### Commands
```bash
uv sync            # install deps incl. dev group
uv run pytest      # run the offline unit suite
uv run ruff check  # lint (line length 100)
```

## Dependencies
- `pytest`, `pytest-asyncio`, `ruff` (dev group).

## Design Decisions
- **Pure-function-first testing**: the highest-risk pure logic (distance math, position extraction, JWT expiry) is unit-tested deterministically and offline; networked layers are deferred.

## Known Risks
- No integration/contract tests for the client, token refresh flow, or tools — regressions in those layers are not caught automatically.
- No CI runs the suite; tests and lint are manual (no `.github/`).

## Extension Guidelines
- Add async coverage for `WunderClient`/`TokenManager` using `httpx.MockTransport` or `respx` — no live API needed; write `async def test_…` (auto-mode handles them).
- Keep tests offline and deterministic; do not call the real Wunder API from the suite.
- Mirror the `test_<module>.py` / `test_<function>_<scenario>` naming when adding files.
