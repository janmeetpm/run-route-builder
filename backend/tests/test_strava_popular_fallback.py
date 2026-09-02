import pytest

from services import strava_service as strava


@pytest.mark.asyncio
async def test_popular_segment_picker_skips_segments_without_endpoints(monkeypatch):
    async def fake_strava_get(token, path, params=None):
        return 200, {
            "segments": [
                {
                    "id": 1,
                    "name": "Missing end",
                    "distance": 300,
                    "athlete_count": 500,
                    "effort_count": 900,
                    "start_latlng": [12.9716, 77.5946],
                },
                {
                    "id": 2,
                    "name": "Good segment",
                    "distance": 450,
                    "athlete_count": 300,
                    "effort_count": 600,
                    "start_latlng": [12.972, 77.595],
                    "end_latlng": [12.974, 77.598],
                },
            ]
        }

    monkeypatch.setattr(strava, "strava_get", fake_strava_get)

    result = await strava.pick_popular_segments_near(
        token="token",
        lon=77.5946,
        lat=12.9716,
        distance_km=5,
    )

    assert [s["id"] for s in result["segments"]] == [2]
    assert result["waypoints"][0] == [77.5946, 12.9716]
    assert result["waypoints"][-1] == [77.5946, 12.9716]


@pytest.mark.asyncio
async def test_popular_segment_picker_returns_empty_when_all_segments_invalid(monkeypatch):
    async def fake_strava_get(token, path, params=None):
        return 200, {
            "segments": [
                {
                    "id": 1,
                    "name": "No endpoints",
                    "distance": 300,
                    "athlete_count": 500,
                    "effort_count": 900,
                }
            ]
        }

    monkeypatch.setattr(strava, "strava_get", fake_strava_get)

    result = await strava.pick_popular_segments_near(
        token="token",
        lon=77.5946,
        lat=12.9716,
        distance_km=5,
    )

    assert result["segments"] == []
    assert result["waypoints"] == []
    assert result["note"] == "no suitable segments"
