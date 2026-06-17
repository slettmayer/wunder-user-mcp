"""Geo helpers: haversine distance and vehicle distance annotation/sorting."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any

_EARTH_RADIUS_KM = 6371.0088

# Candidate field paths where a vehicle's coordinates may live in the API response.
# The first matching pair wins. Confirmed/extended against live responses on first run.
_LAT_KEYS = ("lat", "latitude")
_LNG_KEYS = ("lng", "lon", "longitude")
_NESTED_POSITION_KEYS = ("position", "location", "coordinates", "geometry")


def _from_geojson(obj: dict[str, Any]) -> tuple[float, float] | None:
    """Extract (lat, lng) from a GeoJSON Point-like dict.

    GeoJSON orders coordinates as [longitude, latitude].
    """
    coords = obj.get("coordinates")
    if (
        isinstance(coords, (list, tuple))
        and len(coords) >= 2
        and all(isinstance(c, (int, float)) for c in coords[:2])
    ):
        lng, lat = float(coords[0]), float(coords[1])
        return lat, lng
    return None


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two WGS84 points, in kilometers."""
    rlat1, rlng1, rlat2, rlng2 = map(radians, (lat1, lng1, lat2, lng2))
    dlat = rlat2 - rlat1
    dlng = rlng2 - rlng1
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlng / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * asin(sqrt(a))


def _coord(obj: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def extract_position(vehicle: dict[str, Any]) -> tuple[float, float] | None:
    """Best-effort extraction of (lat, lng) from a vehicle object.

    Looks for top-level lat/lng-style keys, then common nested containers.
    Returns None when no coordinate pair can be found.
    """
    lat = _coord(vehicle, _LAT_KEYS)
    lng = _coord(vehicle, _LNG_KEYS)
    if lat is not None and lng is not None:
        return lat, lng

    for key in _NESTED_POSITION_KEYS:
        nested = vehicle.get(key)
        if isinstance(nested, dict):
            lat = _coord(nested, _LAT_KEYS)
            lng = _coord(nested, _LNG_KEYS)
            if lat is not None and lng is not None:
                return lat, lng
            geojson = _from_geojson(nested)
            if geojson is not None:
                return geojson
    return None


def attach_distance_and_sort(
    vehicles: list[dict[str, Any]], user_lat: float, user_lng: float
) -> list[dict[str, Any]]:
    """Annotate each vehicle with distance from the user and sort ascending.

    Adds `distanceKm` and `distanceMeters` (rounded). Vehicles whose position
    cannot be determined get a null distance and sort last.
    """
    annotated: list[dict[str, Any]] = []
    for vehicle in vehicles:
        item = dict(vehicle)
        pos = extract_position(vehicle)
        if pos is None:
            item["distanceKm"] = None
            item["distanceMeters"] = None
        else:
            km = haversine_km(user_lat, user_lng, pos[0], pos[1])
            item["distanceKm"] = round(km, 4)
            item["distanceMeters"] = round(km * 1000, 1)
        annotated.append(item)

    annotated.sort(
        key=lambda v: v["distanceKm"] if v["distanceKm"] is not None else float("inf")
    )
    return annotated
