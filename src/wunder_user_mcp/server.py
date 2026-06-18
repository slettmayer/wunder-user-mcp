"""FastMCP server exposing Wunder v2 end-user API tools."""

from __future__ import annotations

import asyncio
from typing import Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP

from wunder_user_mcp.auth import TokenManager
from wunder_user_mcp.client import WunderClient
from wunder_user_mcp.config import Settings, load_settings
from wunder_user_mcp.geo import attach_distance_and_sort

SERVER_INSTRUCTIONS = """\
Tools for the Wunder Mobility v2 end-user (User) API. Every call acts on behalf of a
single signed-in end user (authenticated from a refresh token configured on the server);
there is no user/account parameter and you cannot switch users.

Typical flow:
  1. get_vehicles to find a vehicle (pass the user's latitude/longitude to get
     distance-sorted results).
  2. create_rental to reserve (RESERVATION) or immediately start (ACTIVE) a rental for a
     chosen vehicle.
  3. rental_command to operate the rental (START / PARK / DRIVE / END / OPEN_TAILBOX / ...).
  4. get_active_rental any time to see the current ongoing rental(s) and get the
     rental_id needed by rental_command.

Key constraints:
- A user can have only ONE active rental at a time; creating another while one is ACTIVE
  is rejected by the API. Call get_active_rental before creating a new rental.
- create_rental (especially start_rental_state=ACTIVE) and rental_command END are
  high-impact: they trigger vehicle commands, pricing, payment authorization/capture,
  deposits, and invoices. Confirm intent before issuing them.
- Errors are surfaced verbatim from the API, including the Wunder errorCode and
  userMessage; relay those to the user rather than guessing.
"""

mcp = FastMCP("wunder-user-mcp", instructions=SERVER_INSTRUCTIONS)

# Lazily-built, event-loop-bound singletons. Settings are validated eagerly in main().
_settings: Settings | None = None
_client: WunderClient | None = None
_client_lock = asyncio.Lock()


def _require_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


async def _get_client() -> WunderClient:
    """Build (once) and return the shared WunderClient bound to the running loop."""
    global _client
    if _client is not None:
        return _client
    async with _client_lock:
        if _client is None:
            settings = _require_settings()
            http = httpx.AsyncClient(timeout=settings.http_timeout)
            tokens = TokenManager(settings, http)
            _client = WunderClient(settings, http, tokens)
    return _client


@mcp.tool()
async def get_vehicles(
    latitude: float | None = None,
    longitude: float | None = None,
    radius_miles: float | None = None,
    branch_id: int | None = None,
    category_ids: list[int] | None = None,
    exclude_stationed_vehicles: bool | None = None,
    min_state_of_charge: int | None = None,
    max_state_of_charge: int | None = None,
) -> dict[str, Any]:
    """List available vehicles for the signed-in user.

    When both `latitude` and `longitude` are supplied, the result is scoped to a
    radius around that point (`radius_miles`, defaulting to WUNDER_DEFAULT_RADIUS_MI),
    each vehicle is annotated with `distanceKm`/`distanceMeters` from the user, and the
    list is sorted by ascending distance. Without a location, vehicles are returned as
    provided by the API (no distance, no distance sort).

    Filters: `branch_id`, `category_ids`, `exclude_stationed_vehicles` (true = free-floating
    only), `min_state_of_charge`/`max_state_of_charge` (battery percentage 0-100).
    """
    settings = _require_settings()
    client = await _get_client()

    has_lat = latitude is not None
    has_lng = longitude is not None
    if has_lat != has_lng:
        raise ValueError("Provide both latitude and longitude, or neither.")

    params: dict[str, Any] = {
        "branchId": branch_id if branch_id is not None else settings.branch_id,
        "categoryId": category_ids,
        "excludeStationedVehicles": exclude_stationed_vehicles,
        "minStateOfCharge": min_state_of_charge,
        "maxStateOfCharge": max_state_of_charge,
    }

    located = has_lat and has_lng
    if located:
        rad = radius_miles if radius_miles is not None else settings.default_radius_mi
        params.update({"lat": latitude, "lng": longitude, "rad": rad})

    vehicles = await client.list_vehicles(params)

    if located:
        vehicles = attach_distance_and_sort(vehicles, latitude, longitude)  # type: ignore[arg-type]

    return {
        "count": len(vehicles),
        "sortedByDistance": located,
        "vehicles": vehicles,
    }


@mcp.tool()
async def get_active_rental() -> dict[str, Any]:
    """Retrieve the signed-in user's currently ongoing rental(s).

    Returns rentals in `ACTIVE` (trip in progress) or `RESERVATION` (held, not yet
    started) state. Usually 0 or 1. Use a returned rental's `id` with `rental_command`
    to operate it.
    """
    client = await _get_client()
    # Newest first; a small page is enough to capture any active/reserved rentals.
    rentals = await client.list_rentals({"page": 0, "size": 20, "sort": "id,desc"})
    active = [r for r in rentals if r.get("state") in ("ACTIVE", "RESERVATION")]
    return {"count": len(active), "rentals": active}


@mcp.tool()
async def rental_command(
    rental_id: int,
    operation_type: str,
    file_id: int | None = None,
    parking_report: dict[str, Any] | None = None,
    vehicle_code: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Execute an operation on a rental and return the updated rental.

    `operation_type` (case-sensitive) is one of:
      - START             start a reserved rental
      - PARK              pause driving while keeping the rental active
      - DRIVE             resume driving after a park
      - END               end the rental (triggers final checks and billing)
      - OPEN_TAILBOX      open a configured tailbox / helmet box / saddle compartment
      - RENEW_RESERVATION extend a reservation where supported
    Other operation types configured for the tenant are passed through as-is.

    Optional fields are forwarded when relevant (mainly for END): `file_id` (e.g. a
    parking photo uploaded via POST /files), `parking_report`, `vehicle_code`, `reason`.

    Note: ending may be blocked by end-checks (parking/station/photo/surcharge). This
    tool does not pre-run POST /rentals/{id}/check/end; an END that fails a requirement
    surfaces the API error.
    """
    client = await _get_client()
    body: dict[str, Any] = {"operationType": operation_type}
    if file_id is not None:
        body["fileId"] = file_id
    if parking_report is not None:
        body["parkingReport"] = parking_report
    if vehicle_code is not None:
        body["vehicleCode"] = vehicle_code
    if reason is not None:
        body["reason"] = reason
    return await client.rental_operation(rental_id, body)


@mcp.tool()
async def create_rental(
    vehicle_id: int | None = None,
    vehicle_code: str | None = None,
    start_rental_state: Literal["RESERVATION", "ACTIVE"] = "RESERVATION",
    additions: list[str] | None = None,
    user_group_code: str | None = None,
    rental_type: str | None = None,
) -> dict[str, Any]:
    """Create a rental for the signed-in user, as a reservation or an active rental.

    Provide exactly one of `vehicle_id` (from the map/list) or `vehicle_code` (from a
    QR scan). `start_rental_state` is `RESERVATION` (hold the vehicle, default) or
    `ACTIVE` (start the trip immediately, begins billing).

    Optional: `additions` (selected add-on codes, e.g. ["INSURANCE", "HELMET"]),
    `user_group_code` + `rental_type="BUSINESS"` for business-account billing.

    Returns the created rental, including its `id` and `state`.
    """
    if (vehicle_id is None) == (vehicle_code is None):
        raise ValueError("Provide exactly one of vehicle_id or vehicle_code.")
    if start_rental_state not in ("RESERVATION", "ACTIVE"):
        raise ValueError("start_rental_state must be 'RESERVATION' or 'ACTIVE'.")

    client = await _get_client()
    body: dict[str, Any] = {"startRentalState": start_rental_state}
    if vehicle_id is not None:
        body["vehicleId"] = vehicle_id
    if vehicle_code is not None:
        body["vehicleCode"] = vehicle_code
    if additions:
        body["additions"] = additions
    if user_group_code is not None:
        body["userGroupCode"] = user_group_code
    if rental_type is not None:
        body["type"] = rental_type
    return await client.create_rental(body)


def main() -> None:
    """Validate config, then run the MCP server over stdio."""
    _require_settings()  # fail fast on missing env before serving
    mcp.run()


if __name__ == "__main__":
    main()
