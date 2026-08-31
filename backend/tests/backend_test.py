"""Trailscribe backend API tests.

Modules covered:
- health: GET /api/
- discovery (mock strava): GET /api/discovery
- route generation (ORS + LLM): POST /api/routes/generate
- saved routes: POST /api/routes/save, GET /api/routes/saved
"""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

GEN_TIMEOUT = 180

BLR_PAYLOAD = {
    "start_name": "Cubbon Park Gate 4, Bengaluru",
    "start_lon": 77.5946,
    "start_lat": 12.9762,
    "distance_km": 5,
    "pace_group": "easy",
    "provider": "claude",
    "constraints": {
        "loop": True,
        "water_stop": True,
        "avoid_highways": True,
        "well_lit": True,
        "start_time": "05:30",
    },
}


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def generated_claude(api):
    r = api.post(f"{BASE_URL}/api/routes/generate", json=BLR_PAYLOAD, timeout=GEN_TIMEOUT)
    return r


@pytest.fixture(scope="session")
def generated_gemini(api):
    payload = dict(BLR_PAYLOAD, provider="gemini")
    r = api.post(f"{BASE_URL}/api/routes/generate", json=payload, timeout=GEN_TIMEOUT)
    return r


# ---------- health ----------
class TestHealth:
    def test_root(self, api):
        r = api.get(f"{BASE_URL}/api/", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ok"
        assert d["service"] == "trailscribe"


# ---------- discovery ----------
class TestDiscovery:
    @pytest.mark.parametrize("city", ["bengaluru", "delhi"])
    def test_discovery_cities(self, api, city):
        r = api.get(f"{BASE_URL}/api/discovery", params={"city": city}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["city"] == city
        assert len(d["routes"]) == 4
        for route in d["routes"]:
            for k in ["id", "name", "city", "distance_km", "difficulty", "start", "vibe", "tags"]:
                assert k in route, f"missing {k}"
            assert isinstance(route["start"]["lon"], (int, float))
            assert isinstance(route["start"]["lat"], (int, float))

    def test_discovery_case_insensitive(self, api):
        r = api.get(f"{BASE_URL}/api/discovery", params={"city": "Delhi"}, timeout=30)
        assert r.status_code == 200
        assert len(r.json()["routes"]) == 4

    def test_discovery_unknown_city_404(self, api):
        r = api.get(f"{BASE_URL}/api/discovery", params={"city": "paris"}, timeout=30)
        assert r.status_code == 404

    def test_discovery_missing_param_422(self, api):
        r = api.get(f"{BASE_URL}/api/discovery", timeout=30)
        assert r.status_code == 422


# ---------- route generation ----------
class TestGenerateClaude:
    def test_status_and_shape(self, generated_claude):
        r = generated_claude
        assert r.status_code == 200, f"body={r.text[:500]}"
        d = r.json()
        for k in [
            "id", "start_name", "start", "distance_km", "duration_s", "elev_stats",
            "coordinates", "elevations", "cumulative_distance_m", "steps", "midpoint",
            "closed", "narration", "llm_guess", "failure_log", "provider", "constraints",
        ]:
            assert k in d, f"missing key {k}"
        assert d["provider"] == "claude"
        assert isinstance(d["closed"], bool)
        assert len(d["midpoint"]) == 2

    def test_geometry(self, generated_claude):
        d = generated_claude.json()
        assert len(d["coordinates"]) > 50, f"only {len(d['coordinates'])} pts"
        assert len(d["elevations"]) == len(d["coordinates"])
        assert len(d["cumulative_distance_m"]) == len(d["coordinates"])
        assert all(len(c) == 2 for c in d["coordinates"][:20])
        assert d["cumulative_distance_m"][0] == 0
        assert d["cumulative_distance_m"][-1] > 0

    def test_distance_within_tolerance(self, generated_claude):
        d = generated_claude.json()
        assert 2.5 <= d["distance_km"] <= 8.0, f"actual={d['distance_km']}"

    def test_elev_stats(self, generated_claude):
        e = generated_claude.json()["elev_stats"]
        for k in ["ascent_m", "descent_m", "min_m", "max_m"]:
            assert k in e
        assert e["ascent_m"] >= 0 and e["descent_m"] >= 0
        assert e["max_m"] >= e["min_m"]

    def test_narration_populated(self, generated_claude):
        n = generated_claude.json()["narration"]
        for k in ["headline", "narration", "segments", "safety_note", "water_stop_pitch"]:
            assert k in n, f"missing narration.{k}"
        assert len(n["headline"]) > 0
        assert len(n["narration"]) > 100, f"narration too short: {n['narration'][:120]}"
        assert isinstance(n["segments"], list) and len(n["segments"]) > 0
        assert len(n["safety_note"]) > 0
        assert len(n["water_stop_pitch"]) > 0

    def test_llm_guess(self, generated_claude):
        g = generated_claude.json()["llm_guess"]
        for k in ["estimated_distance_km", "distance_error_pct", "reasoning", "waypoint_count"]:
            assert k in g
        assert isinstance(g["estimated_distance_km"], (int, float))
        assert isinstance(g["distance_error_pct"], (int, float))
        assert len(g["reasoning"]) > 0

    def test_failure_log(self, generated_claude):
        log = generated_claude.json()["failure_log"]
        assert len(log) >= 2, f"only {len(log)} entries"
        for entry in log:
            assert "stage" in entry and "level" in entry and "message" in entry and "t" in entry
            assert entry["level"] in ["info", "warn", "error", "success"]
        stages = {e["stage"] for e in log}
        assert "llm_geometry_check" in stages
        assert "ors_routing" in stages

    def test_steps_present(self, generated_claude):
        steps = generated_claude.json()["steps"]
        assert isinstance(steps, list) and len(steps) > 0
        assert "instruction" in steps[0]


class TestGenerateGemini:
    def test_status_and_narration(self, generated_gemini):
        r = generated_gemini
        assert r.status_code == 200, f"body={r.text[:500]}"
        d = r.json()
        assert d["provider"] == "gemini"
        n = d["narration"]
        assert len(n["narration"]) > 100, f"gemini narration too short: {n['narration'][:200]}"
        assert len(n["headline"]) > 0
        assert len(d["coordinates"]) > 50
        assert len(d["failure_log"]) >= 2


class TestGenerateValidation:
    def test_missing_fields_422(self, api):
        r = api.post(f"{BASE_URL}/api/routes/generate", json={"distance_km": 5}, timeout=60)
        assert r.status_code == 422

    def test_delhi_generation(self, api):
        payload = dict(
            BLR_PAYLOAD,
            start_name="Connaught Place, Delhi",
            start_lon=77.209,
            start_lat=28.6139,
            distance_km=4,
        )
        r = api.post(f"{BASE_URL}/api/routes/generate", json=payload, timeout=GEN_TIMEOUT)
        assert r.status_code == 200, f"body={r.text[:500]}"
        d = r.json()
        assert len(d["coordinates"]) > 50
        assert d["distance_km"] > 1


# ---------- saved routes ----------
class TestSavedRoutes:
    def test_save_and_list(self, api, generated_claude):
        assert generated_claude.status_code == 200
        d = generated_claude.json()
        payload = {
            "name": "TEST_Saved Route",
            "city": "Bengaluru",
            "distance_km": d["distance_km"],
            "ascent_m": d["elev_stats"]["ascent_m"],
            "provider": d["provider"],
            "coordinates": d["coordinates"],
            "elevations": d["elevations"],
            "cumulative_distance_m": d["cumulative_distance_m"],
            "narration": d["narration"],
            "failure_log": d["failure_log"],
            "midpoint": d["midpoint"],
        }
        r = api.post(f"{BASE_URL}/api/routes/save", json=payload, timeout=60)
        assert r.status_code == 200, r.text[:400]
        body = r.json()
        assert body["saved"] is True
        assert isinstance(body["id"], str) and len(body["id"]) > 0
        saved_id = body["id"]

        lr = api.get(f"{BASE_URL}/api/routes/saved", timeout=30)
        assert lr.status_code == 200
        routes = lr.json()["routes"]
        match = [x for x in routes if x["id"] == saved_id]
        assert match, "saved route not returned by /api/routes/saved"
        got = match[0]
        assert got["name"] == "TEST_Saved Route"
        assert got["city"] == "Bengaluru"
        assert got["distance_km"] == d["distance_km"]
        assert "_id" not in got, "MongoDB _id leaked in response"
        assert len(got["coordinates"]) == len(d["coordinates"])
        assert "created_at" in got

    def test_save_invalid_payload_422(self, api):
        r = api.post(f"{BASE_URL}/api/routes/save", json={"name": "TEST_bad"}, timeout=30)
        assert r.status_code == 422
