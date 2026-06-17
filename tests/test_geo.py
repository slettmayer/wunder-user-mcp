from wunder_user_mcp.geo import attach_distance_and_sort, extract_position, haversine_km


def test_haversine_known_distance():
    # Hamburg HBF -> Berlin HBF is ~255 km.
    km = haversine_km(53.5528, 10.0067, 52.5251, 13.3694)
    assert 250 < km < 260


def test_haversine_zero():
    assert haversine_km(48.2, 16.37, 48.2, 16.37) == 0.0


def test_extract_position_variants():
    assert extract_position({"lat": 1.0, "lng": 2.0}) == (1.0, 2.0)
    assert extract_position({"latitude": 1.0, "longitude": 2.0}) == (1.0, 2.0)
    assert extract_position({"position": {"latitude": 3.0, "longitude": 4.0}}) == (3.0, 4.0)
    assert extract_position({"foo": "bar"}) is None


def test_extract_position_geojson_point():
    # GeoJSON orders coordinates as [longitude, latitude].
    vehicle = {"position": {"type": "Point", "coordinates": [16.3381, 48.2099]}}
    assert extract_position(vehicle) == (48.2099, 16.3381)


def test_attach_distance_and_sort_orders_ascending_and_pushes_unknown_last():
    user_lat, user_lng = 48.2085, 16.3721  # Vienna
    vehicles = [
        {"id": "far", "lat": 48.30, "lng": 16.50},
        {"id": "near", "lat": 48.21, "lng": 16.37},
        {"id": "unknown"},  # no position
    ]
    result = attach_distance_and_sort(vehicles, user_lat, user_lng)
    assert [v["id"] for v in result] == ["near", "far", "unknown"]
    assert result[0]["distanceMeters"] is not None
    assert result[-1]["distanceKm"] is None
    # original input is not mutated
    assert "distanceKm" not in vehicles[0]
