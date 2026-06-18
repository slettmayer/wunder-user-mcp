# MCP Tools

## Purpose
Documents the four MCP tools the server exposes — the product surface — including how they are registered, their parameters, the snake_case→camelCase mapping, and the server-level instructions sent to clients.

## Responsibilities
- Describe each `@mcp.tool()` function in `server.py` and the API endpoint it maps to.
- Record argument validation and request-body construction per tool.
- Record `SERVER_INSTRUCTIONS` and the high-impact-operation guardrail.

## Non-Responsibilities
- The HTTP request path and retry — see [ARCHITECTURE.md](ARCHITECTURE.md).
- Token handling — see [AUTHENTICATION.md](AUTHENTICATION.md).
- Domain meaning of rental states/operations — see [docs/domain/OVERVIEW.md](../domain/OVERVIEW.md).

## Overview

### Registration
`server.py` builds one module-level instance: `mcp = FastMCP("wunder-user-mcp", instructions=SERVER_INSTRUCTIONS)`. Each tool is an `async` module-level function decorated with `@mcp.tool()`; its docstring and type-annotated signature become the schema the client sees. `main()` validates settings, then calls `mcp.run()` (stdio).

### The four tools

| Tool | Endpoint | Maps to client method |
|------|----------|-----------------------|
| `get_vehicles` | `GET /vehicles` | `WunderClient.list_vehicles` |
| `get_active_rental` | `GET /rentals` | `WunderClient.list_rentals` |
| `rental_command` | `POST /rentals/{id}/operation` | `WunderClient.rental_operation` |
| `create_rental` | `POST /rentals` | `WunderClient.create_rental` |

#### `get_vehicles`
Params (all optional): `latitude`, `longitude`, `radius_miles`, `branch_id`, `category_ids: list[int]`, `exclude_stationed_vehicles: bool`, `min_state_of_charge`, `max_state_of_charge`.
- Validation: `latitude` and `longitude` must be supplied together or not at all.
- When located, adds `lat`/`lng`/`rad` query params (radius defaults to `settings.default_radius_mi`), then post-processes the response through `geo.attach_distance_and_sort()` to add `distanceKm`/`distanceMeters` and sort ascending.
- `branch_id` falls back to `settings.branch_id`. Param mapping: `category_ids`→`categoryId`, `exclude_stationed_vehicles`→`excludeStationedVehicles`, `min/max_state_of_charge`→`min/maxStateOfCharge`.
- Returns `{count, sortedByDistance, vehicles}`.

#### `get_active_rental`
No params. Queries `GET /rentals` with `{page:0, size:20, sort:"id,desc"}`, then filters to `state in ("ACTIVE", "RESERVATION")`. Returns `{count, rentals}`. Use a returned rental's `id` with `rental_command`.

#### `rental_command`
Params: `rental_id: int` (required), `operation_type: str` (required), and optional `file_id`, `parking_report`, `vehicle_code`, `reason`.
- Documented `operation_type` values: `START`, `PARK`, `DRIVE`, `END`, `OPEN_TAILBOX`, `RENEW_RESERVATION`. Other tenant-configured operations are passed through as-is (the string is not enum-restricted).
- Body: `{operationType}` plus any provided optional fields, mapped `file_id`→`fileId`, `parking_report`→`parkingReport`, `vehicle_code`→`vehicleCode`, `reason`→`reason`.
- Does NOT pre-run `POST /rentals/{id}/check/end`; a failing end-check surfaces as a `WunderApiError`.

#### `create_rental`
Params: `vehicle_id: int | None`, `vehicle_code: str | None`, `start_rental_state: Literal["RESERVATION","ACTIVE"] = "RESERVATION"`, `additions: list[str] | None`, `user_group_code: str | None`, `rental_type: str | None`.
- Validation: exactly one of `vehicle_id`/`vehicle_code`; `start_rental_state` re-checked against the two allowed values.
- Body: `{startRentalState}` plus `vehicleId`/`vehicleCode`, optional `additions`, `userGroupCode`, and `type` (from `rental_type`). Returns the created rental (`id`, `state`).

### Server instructions
`SERVER_INSTRUCTIONS` (passed as `FastMCP(instructions=…)`) tells the client: the typical flow (`get_vehicles` → `create_rental` → `rental_command` → `get_active_rental`), the one-active-rental constraint, the high-impact-operation warning, and to relay API errors verbatim.

## Dependencies
- `geo.attach_distance_and_sort` (vehicle distance sorting).
- `WunderClient` for all endpoint calls; `Settings` for branch/radius defaults.

## Design Decisions
- **`operation_type` is a free string, not an enum**, so tenant-specific operations beyond the documented set keep working without a code change.
- **`start_rental_state` IS a strict `Literal`** because the two states are universal and a typo there is high-impact.
- **Distance sorting is server-side post-processing**, not an API param, so it works regardless of how a tenant nests vehicle coordinates (see [docs/domain/OVERVIEW.md](../domain/OVERVIEW.md)).

## Known Risks
- `create_rental(ACTIVE)` and `rental_command(END)` are high-impact (vehicle commands, payments, deposits, invoices); the guardrail is advisory text in `SERVER_INSTRUCTIONS`, not enforced in code.

## Extension Guidelines
- Add a tool as an `@mcp.tool()` async function: validate args with `ValueError`, build a `camelCase` body/params dict, delegate to a `WunderClient` method, return a `dict`.
- Keep the docstring accurate and example-led — it is the schema the LLM reads.
- If a new operation must be guaranteed, validate it explicitly rather than relying on pass-through.
