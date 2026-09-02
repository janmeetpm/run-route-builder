"""Regression tests for 'Route through popular Strava paths'.

The reported symptom was that this option almost always errored. Two causes:
a single unroutable Strava segment endpoint 400s the entire ORS request, and
/segments/explore returns no popularity counts so the "most-run" sort was
sorting zeros.
"""
import pytest

from services import route_service as rs
from services import strava_service as strava


ORS_UNROUTABLE = (
    "ORS error 404: {'error': {'code': 2010, 'message': 'Could not find "
    "routable point within a radius of 350.0 meters of specified "
    "coordinate 3: 77.6010000 12.9750000.'}}"
)


def _geojson(n_coords: int = 5, distance_m: float = 5100.0):
    coords = [[77.59 + i * 0.001, 12.97 + i * 0.001, 900.0 + i] for i in range(n_coords)]
    return {
        "features": [{
            "geometry": {"coordinates": coords},
            "properties": {"summary": {"distance": distance_m, "duration": 3000.0}, "segments": []},
        }]
    }


@pytest.fixture
def no_snap(monkeypatch):
    """Snapping unavailable — isolates the drop-retry behaviour."""
    async def fake_snap(coordinates, radius_m=rs.SNAP_RADIUS_M):
        return None
    monkeypatch.setattr(rs, "_snap_to_network", fake_snap)


# ---------------- the actual fix: don't lose the route to one bad point ----------------

@pytest.mark.asyncio
async def test_unroutable_waypoint_is_dropped_and_route_still_returned(monkeypatch, no_snap):
    calls = []

    async def fake_post(body):
        calls.append(list(body["coordinates"]))
        if len(calls) == 1:
            raise RuntimeError(ORS_UNROUTABLE)
        return _geojson()

    monkeypatch.setattr(rs, "_post_ors", fake_post)

    waypoints = [
        [77.5946, 12.9716],   # 0 start anchor
        [77.5980, 12.9730],   # 1
        [77.5995, 12.9740],   # 2
        [77.6010, 12.9750],   # 3 <- ORS says unroutable
        [77.6030, 12.9770],   # 4
        [77.5946, 12.9716],   # 5 end anchor
    ]
    route = await rs.generate_waypoint_route(waypoints)

    assert len(calls) == 2, "should retry once after dropping the bad waypoint"
    assert [77.6010, 12.9750] not in calls[1]
    assert calls[1][0] == [77.5946, 12.9716], "start anchor preserved"
    assert calls[1][-1] == [77.5946, 12.9716], "end anchor preserved"
    assert route["distance_m"] == 5100.0
    assert route["waypoints_dropped"] == 1
    assert route["waypoints_requested"] == 6


@pytest.mark.asyncio
async def test_several_unroutable_waypoints_are_dropped_in_turn(monkeypatch, no_snap):
    bad = {tuple([77.5980, 12.9730]), tuple([77.6010, 12.9750])}
    calls = []

    async def fake_post(body):
        coords = body["coordinates"]
        calls.append(list(coords))
        for i, c in enumerate(coords):
            if tuple(c) in bad:
                raise RuntimeError(
                    f"ORS error 404: Could not find routable point within a radius "
                    f"of 350.0 meters of specified coordinate {i}: {c[0]} {c[1]}."
                )
        return _geojson()

    monkeypatch.setattr(rs, "_post_ors", fake_post)

    route = await rs.generate_waypoint_route([
        [77.5946, 12.9716],
        [77.5980, 12.9730],
        [77.5995, 12.9740],
        [77.6010, 12.9750],
        [77.6030, 12.9770],
        [77.5946, 12.9716],
    ])

    assert route["waypoints_dropped"] == 2
    assert all(tuple(c) not in bad for c in calls[-1])


@pytest.mark.asyncio
async def test_unroutable_start_anchor_is_not_silently_dropped(monkeypatch, no_snap):
    """The runner's own start point failing is a real failure — surface it so
    the endpoint falls back to a normal loop instead of routing from elsewhere."""
    async def fake_post(body):
        raise RuntimeError(
            "ORS error 404: Could not find routable point within a radius of "
            "350.0 meters of specified coordinate 0: 77.5946 12.9716."
        )

    monkeypatch.setattr(rs, "_post_ors", fake_post)

    with pytest.raises(RuntimeError):
        await rs.generate_waypoint_route([
            [77.5946, 12.9716], [77.5980, 12.9730], [77.5946, 12.9716],
        ])


@pytest.mark.asyncio
async def test_non_routability_errors_are_not_retried(monkeypatch, no_snap):
    """A rate limit or bad key must propagate immediately, not burn retries."""
    calls = []

    async def fake_post(body):
        calls.append(1)
        raise RuntimeError("ORS error 403: {'error': 'Daily quota exceeded'}")

    monkeypatch.setattr(rs, "_post_ors", fake_post)

    with pytest.raises(RuntimeError):
        await rs.generate_waypoint_route([
            [77.5946, 12.9716], [77.5980, 12.9730], [77.5946, 12.9716],
        ])
    assert len(calls) == 1


# ---------------- supporting behaviour ----------------

@pytest.mark.asyncio
async def test_coincident_waypoints_are_collapsed_before_routing(monkeypatch, no_snap):
    """Adjacent segments sharing an endpoint produce a zero-length leg."""
    calls = []

    async def fake_post(body):
        calls.append(list(body["coordinates"]))
        return _geojson()

    monkeypatch.setattr(rs, "_post_ors", fake_post)

    await rs.generate_waypoint_route([
        [77.5946, 12.9716],
        [77.5980, 12.9730],
        [77.59800, 12.97301],   # ~1 m from the previous point
        [77.6030, 12.9770],
        [77.5946, 12.9716],
    ])

    assert len(calls[0]) == 4, "the duplicate intermediate point is collapsed"
    assert calls[0][-1] == [77.5946, 12.9716]


@pytest.mark.asyncio
async def test_snapped_coordinates_are_used_and_unsnappable_ones_dropped(monkeypatch):
    calls = []

    async def fake_snap(coordinates, radius_m=rs.SNAP_RADIUS_M):
        out = []
        for c in coordinates:
            if c == [77.5995, 12.9740]:
                out.append(None)            # nothing routable nearby
            else:
                out.append([c[0] + 0.0001, c[1] + 0.0001])
        return out

    async def fake_post(body):
        calls.append(list(body["coordinates"]))
        return _geojson()

    monkeypatch.setattr(rs, "_snap_to_network", fake_snap)
    monkeypatch.setattr(rs, "_post_ors", fake_post)

    await rs.generate_waypoint_route([
        [77.5946, 12.9716], [77.5980, 12.9730], [77.5995, 12.9740], [77.5946, 12.9716],
    ])

    sent = calls[0]
    assert [77.5995, 12.9740] not in sent
    assert sent[0] == [77.5947, 12.9717], "start snapped onto the network"


@pytest.mark.asyncio
async def test_snap_failure_falls_back_to_raw_coordinates(monkeypatch):
    """The snap endpoint is optional; its absence must not break routing."""
    calls = []

    def boom(*a, **k):
        raise RuntimeError("snap endpoint unavailable")

    async def fake_post(body):
        calls.append(list(body["coordinates"]))
        return _geojson()

    monkeypatch.setattr(rs.httpx, "AsyncClient", boom)
    monkeypatch.setattr(rs, "_post_ors", fake_post)
    monkeypatch.setenv("ORS_API_KEY", "test-key")

    route = await rs.generate_waypoint_route([
        [77.5946, 12.9716], [77.5980, 12.9730], [77.5946, 12.9716],
    ])
    assert route["distance_m"] == 5100.0
    assert calls[0][1] == [77.5980, 12.9730], "raw coordinate used unchanged"


# ---------------- popularity actually being populated ----------------

@pytest.mark.asyncio
async def test_explore_segments_get_real_popularity_counts(monkeypatch):
    """/segments/explore omits athlete_count, so the picker must fetch it and
    select on it — otherwise 'most-run' picks arbitrarily.

    Note the returned `segments` list is ordered geographically (it doubles as
    the waypoint order), so popularity shows up in *which* segments are
    picked, not in their order.
    """
    detail = {
        101: {"athlete_count": 40, "effort_count": 90},
        102: {"athlete_count": 9000, "effort_count": 41000},
        103: {"athlete_count": 5000, "effort_count": 12000},
    }
    fetched = []

    async def fake_strava_get(token, path, params=None):
        if path == "/segments/explore":
            return 200, {"segments": [
                {   # explore payload shape: no counts at all
                    "id": 101, "name": "Quiet lane", "distance": 1400,
                    "start_latlng": [12.9716, 77.5946], "end_latlng": [12.9730, 77.5980],
                },
                {
                    "id": 102, "name": "Cubbon Park loop", "distance": 1400,
                    "start_latlng": [12.9750, 77.5920], "end_latlng": [12.9770, 77.5900],
                },
                {
                    "id": 103, "name": "Lalbagh west", "distance": 1400,
                    "start_latlng": [12.9600, 77.5850], "end_latlng": [12.9610, 77.5860],
                },
            ]}
        seg_id = int(path.rsplit("/", 1)[-1])
        fetched.append(seg_id)
        return 200, detail[seg_id]

    monkeypatch.setattr(strava, "strava_get", fake_strava_get)

    result = await strava.pick_popular_segments_near(
        token="t", lon=77.5946, lat=12.9716, distance_km=5,
    )

    assert sorted(fetched) == [101, 102, 103], "counts fetched for every candidate"
    picked = {s["id"] for s in result["segments"]}
    assert picked == {102, 103}, "the two most-run segments are threaded"
    assert 101 not in picked, "least-run segment dropped despite being nearest"
    counts = {s["id"]: s["athlete_count"] for s in result["segments"]}
    assert counts[102] == 9000


@pytest.mark.asyncio
async def test_segment_detail_failures_do_not_break_the_pick(monkeypatch):
    async def fake_strava_get(token, path, params=None):
        if path == "/segments/explore":
            return 200, {"segments": [{
                "id": 101, "name": "Quiet lane", "distance": 600,
                "start_latlng": [12.9716, 77.5946], "end_latlng": [12.9730, 77.5980],
            }]}
        return 429, {"message": "Rate Limit Exceeded"}

    monkeypatch.setattr(strava, "strava_get", fake_strava_get)

    result = await strava.pick_popular_segments_near(
        token="t", lon=77.5946, lat=12.9716, distance_km=5,
    )
    assert [s["id"] for s in result["segments"]] == [101]
    assert result["segments"][0]["athlete_count"] == 0
