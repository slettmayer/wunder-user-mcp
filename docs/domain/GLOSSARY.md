# Glossary

## Purpose
Defines the domain and API terminology used across the codebase, tools, and documentation, so terms are used consistently.

## Responsibilities
- Define each domain/API term in one place.

## Non-Responsibilities
- Entity relationships and lifecycle — see [OVERVIEW.md](OVERVIEW.md).
- Tool parameters that use these terms — see [docs/tech/MCP-TOOLS.md](../tech/MCP-TOOLS.md).

## Overview

### Terms

- **Tenant short-code** — string namespacing all API paths for one Wunder operator. Set via `WUNDER_TENANT`; appears as `/{tenant}/auth/…` and `/{tenant}/front/…`.
- **Branch** — integer-id subdivision (zone/depot) within a tenant; `WUNDER_BRANCH_ID`. Optional scoping for vehicle/rental queries.
- **front endpoint** — the `/front` path segment denoting the end-user-facing API (`/{tenant}/front/vehicles`, `/{tenant}/front/rentals`), as opposed to operator/admin APIs. `WunderClient` wraps these.
- **RESERVATION** — rental state: the vehicle is held for the user but the trip clock and billing have not started. Requires `START` to begin the trip.
- **ACTIVE** — rental state: the trip is in progress and billing is running. Allows `PARK`, `DRIVE`, `OPEN_TAILBOX`, `END`.
- **vehicle_id** — integer primary key of a vehicle from the list/map API; one of the two ways to identify a vehicle in `create_rental`.
- **vehicle_code** — short alphanumeric string physically printed/QR-encoded on the vehicle; the other way to identify a vehicle (mutually exclusive with `vehicle_id`).
- **operationType** — the command string passed to `POST /rentals/{id}/operation`. Documented set: `START`, `PARK`, `DRIVE`, `END`, `OPEN_TAILBOX`, `RENEW_RESERVATION`; tenant-specific operations pass through as-is.
- **refresh token** — long-lived credential (`WUNDER_REFRESH_TOKEN`) proving user identity. Exchanged for short-lived access tokens. Obtained once via a Wunder sign-in endpoint (`/{tenant}/auth/sign-in-email`, `/sign-in-phone-number`, `/sign-in-api-client`).
- **access token** — short-lived JWT (≈5h) used as the `Bearer` token on every API request; managed internally by `TokenManager`, never exposed to callers. See [docs/tech/AUTHENTICATION.md](../tech/AUTHENTICATION.md).
- **stationed vehicle** — a vehicle that must be returned to a fixed station/dock, vs. a **free-floating** vehicle that can be left anywhere in a zone. Controlled by `exclude_stationed_vehicles` in `get_vehicles`.
- **state of charge** — battery percentage (0–100). Filterable via `min_state_of_charge`/`max_state_of_charge`.
- **addition** — optional add-on selected at rental creation, by string code (e.g. `INSURANCE`, `HELMET`); passed in `additions`.
- **user group / rental type** — `user_group_code` plus `rental_type="BUSINESS"` routes a rental to a business account rather than personal billing.
- **end-check** — server-side validation gate the API runs before allowing `END` (e.g. valid parking zone, station return, photo, surcharge). This server does not pre-run `POST /rentals/{id}/check/end`.
- **parking report** — structured end-of-trip data submitted with `END` (`parking_report`), and `file_id` referencing a file uploaded via `POST /files` (not exposed as a tool here).
- **errorCode / userMessage** — structured fields in Wunder API error bodies, joined by `_safe_error_detail` and surfaced verbatim to the caller.
- **GeoJSON Point** — coordinate format where `coordinates` is `[longitude, latitude]` (longitude first); handled by `geo._from_geojson`.

## Dependencies
- Terms map to fields/params in `server.py`, `client.py`, `config.py`, and `geo.py`.

## Design Decisions
- Terminology mirrors the Wunder API field names (`operationType`, `startRentalState`, `errorCode`) so the docs and the wire format stay aligned.

## Known Risks
- None.

## Extension Guidelines
- When introducing a new domain term or API field, add it here and cross-reference the tool/module that uses it.
