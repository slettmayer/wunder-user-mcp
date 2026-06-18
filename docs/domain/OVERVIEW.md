# Domain Overview

## Purpose
Documents the business domain the server operates in — shared/micro-mobility vehicle rental — its core entities, the rental lifecycle, key constraints, and the external integration.

## Responsibilities
- Classify the domain and enumerate the core entities.
- Describe the rental lifecycle (states and operations) and the high-impact constraints.
- Describe the single upstream integration and the single-user model.

## Non-Responsibilities
- Tool signatures and field mapping — see [docs/tech/MCP-TOOLS.md](../tech/MCP-TOOLS.md).
- Token/auth mechanics — see [docs/tech/AUTHENTICATION.md](../tech/AUTHENTICATION.md).
- Term definitions in isolation — see [GLOSSARY.md](GLOSSARY.md).

## Overview

### Domain
Shared / micro-mobility vehicle rental SaaS. The server gives an AI agent or MCP client structured, safe access to one signed-in end user's slice of a Wunder Mobility (product name: Gourban) operator: discover nearby vehicles, reserve or start a trip, operate the vehicle during the trip, and end it.

### Core entities
- **Vehicle** — a rentable asset. Two distinct keys: `vehicle_id` (integer, from the list/map API) and `vehicle_code` (string, from a physical QR scan). Carries a geospatial position used for proximity sorting. Filterable by branch, category, free-floating vs. stationed, and battery state-of-charge.
- **Rental** — the core transactional entity (`GET/POST /rentals`, `POST /rentals/{id}/operation`). Has a numeric `id` and a `state` (`RESERVATION` or `ACTIVE`).
- **Reservation** — a rental in `RESERVATION` state: the vehicle is held but the trip/billing has not started. Converted to a trip with the `START` operation; extendable with `RENEW_RESERVATION`.
- **Tenant** — a Wunder operator (mobility company / city program). The tenant short-code (`WUNDER_TENANT`) is embedded in every URL (`/{tenant}/auth/…`, `/{tenant}/front/…`). One server instance serves exactly one tenant.
- **Branch** — an integer-id subdivision (zone/depot) within a tenant; optional scoping (`WUNDER_BRANCH_ID`). Omitted → tenant-wide results.
- **User** — the end user, identified implicitly by `WUNDER_REFRESH_TOKEN`. No user parameter on any tool; one server instance = one user, no switching.
- **Addition** — optional add-on selected at creation, by string code (e.g. `INSURANCE`, `HELMET`).

### Rental lifecycle
```
create_rental(RESERVATION) --> RESERVATION --START--> ACTIVE --END--> (ended; billed)
create_rental(ACTIVE) ------------------------------> ACTIVE
ACTIVE --PARK--> (paused) --DRIVE--> ACTIVE
RESERVATION --RENEW_RESERVATION--> RESERVATION (extended)
ACTIVE/RESERVATION --OPEN_TAILBOX--> (compartment opened)
```
- **Operations** are issued via `rental_command` with an `operation_type`: `START`, `PARK`, `DRIVE`, `END`, `OPEN_TAILBOX`, `RENEW_RESERVATION`, plus any tenant-specific operations (passed through).
- **End-checks**: ending may be gated server-side (valid parking zone, station return, photo, surcharge). This server does not pre-run `POST /rentals/{id}/check/end`; a failed check surfaces as an API error.

### Constraints (domain rules)
- **One active rental per user**: creating a rental while one is `ACTIVE` is rejected by the API. Call `get_active_rental` first.
- **High-impact operations**: `create_rental` with `start_rental_state=ACTIVE` and `rental_command` with `END` trigger real vehicle hardware commands, pricing, payment authorization/capture, deposit holds, and invoices. Confirm intent before issuing.
- **Verbatim errors**: the Wunder API returns structured `errorCode`/`userMessage`; the server relays these unchanged so the caller can surface the operator's exact message.

### Vehicle discovery & geo
When a caller passes `latitude`/`longitude`, `get_vehicles` scopes to a radius and annotates each vehicle with `distanceKm`/`distanceMeters`, sorting ascending. Coordinates are extracted best-effort from several layouts (flat `lat`/`lng` or `latitude`/`longitude`; nested `position`/`location`/`coordinates`/`geometry`; GeoJSON `Point` with longitude-first `coordinates`). Vehicles whose position cannot be determined sort last.

## Dependencies
- **Wunder Mobility v2 User API** — the sole upstream. Production `https://go.api.gourban.services/v1`; staging `https://go-staging.api.gourban.services/v1`. URL shape: `/{tenant}/auth/…` (auth) and `/{tenant}/front/…` (end-user). A staging tenant on the production host returns `404`.

## Design Decisions
- **Single-user, single-tenant per process**: the refresh-token-as-identity model deliberately prevents cross-user access and keeps the tool surface parameter-free.
- **Advisory high-impact guardrail**: the constraint is communicated via `SERVER_INSTRUCTIONS`, leaving final confirmation to the calling agent/human.

## Known Risks
- No compliance controls (GDPR/PCI/SOC2) live in this codebase; it is a thin proxy and any such obligations sit upstream in the Wunder platform.
- Best-effort position extraction may miss a tenant whose response uses different field names — extend `geo.py` if so.

## Extension Guidelines
- New entities/operations should be reflected here and in [GLOSSARY.md](GLOSSARY.md), with tool-level detail in [docs/tech/MCP-TOOLS.md](../tech/MCP-TOOLS.md).
- If a tenant's vehicle position layout is unsupported, add the field path to `geo.py`'s candidate keys rather than special-casing in the tool.
