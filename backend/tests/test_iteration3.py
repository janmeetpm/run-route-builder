"""Iteration 3 regression tests for Trailscribe.

Focus (fixes claimed by main agent):
- llm_narration failure_log level derived from _parse_ok (warn + 'Narration JSON unparseable' prefix)
- weather failure_log level derived from has_any (warn when temp+sunrise+aqi all None)
- POST /api/routes/save persists `weather`
- Delhi payload stays in Delhi bounds
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
PLACEHOLDER = "Route narration unavailable"

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

REPEATS = 3


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def repeat_runs(api):
    """Generate the same route REPEATS times (LLM parse fallback was intermittent)."""
    runs = []
    for i in range(REPEATS):
        r = api.post(f"{BASE_URL}/api/routes/generate", json=BLR_PAYLOAD, timeout=GEN_TIMEOUT)
        runs.append(r)
    return runs


# ---------- narration parse-ok signal ----------
class TestNarrationParseSignal:
    def test_all_runs_200(self, repeat_runs):
        codes = [r.status_code for r in repeat_runs]
        assert all(c == 200 for c in codes), f"status codes={codes}"

    def test_narration_populated_repeatedly(self, repeat_runs):
        failures = []
        for i, r in enumerate(repeat_runs):
            n = r.json()["narration"]
            for k in ["headline", "narration", "segments", "safety_note", "water_stop_pitch"]:
                if k not in n:
                    failures.append(f"run{i}: missing narration.{k}")
            if PLACEHOLDER in n.get("narration", ""):
                failures.append(f"run{i}: placeholder narration served (parse fallback)")
            if len(n.get("narration", "")) <= 100:
                failures.append(f"run{i}: narration too short: {n.get('narration','')[:100]}")
            if not isinstance(n.get("segments"), list) or not n.get("segments"):
                failures.append(f"run{i}: segments empty")
        assert not failures, "; ".join(failures)

    def test_narration_log_level_matches_content(self, repeat_runs):
        """level must be 'success' for real narration, 'warn' + prefix for the fallback."""
        problems = []
        for i, r in enumerate(repeat_runs):
            d = r.json()
            entries = [e for e in d["failure_log"] if e["stage"] == "llm_narration"]
            if not entries:
                problems.append(f"run{i}: no llm_narration entry in failure_log")
                continue
            e = entries[0]
            is_fallback = PLACEHOLDER in d["narration"].get("narration", "")
            if is_fallback:
                if e["level"] != "warn":
                    problems.append(f"run{i}: fallback narration logged level={e['level']} (expected warn)")
                if not e["message"].startswith("Narration JSON unparseable"):
                    problems.append(f"run{i}: fallback message wrong prefix: {e['message'][:120]}")
            else:
                if e["level"] != "success":
                    problems.append(f"run{i}: good narration logged level={e['level']} msg={e['message'][:120]}")
        assert not problems, "; ".join(problems)

    def test_no_internal_parse_keys_leak_break_shape(self, repeat_runs):
        """_parse_ok/_parse_error are internal signals; if present they must be booleans/strings."""
        for i, r in enumerate(repeat_runs):
            n = r.json()["narration"]
            if "_parse_ok" in n:
                assert isinstance(n["_parse_ok"], bool), f"run{i}: _parse_ok not bool"


# ---------- weather level derivation ----------
class TestWeatherLogLevel:
    def test_weather_level_matches_payload(self, repeat_runs):
        problems = []
        for i, r in enumerate(repeat_runs):
            d = r.json()
            w = d.get("weather")
            entries = [e for e in d["failure_log"] if e["stage"] == "weather"]
            if not entries:
                problems.append(f"run{i}: no weather stage entry")
                continue
            level = entries[0]["level"]
            has_any = bool(w) and any(
                w.get(k) is not None for k in ("temperature_c", "sunrise", "aqi")
            )
            expected = "success" if has_any else "warn"
            if level != expected:
                problems.append(
                    f"run{i}: weather level={level} expected={expected} payload={w}"
                )
        assert not problems, "; ".join(problems)

    def test_weather_keys_present(self, repeat_runs):
        for i, r in enumerate(repeat_runs):
            d = r.json()
            assert "weather" in d, f"run{i}: no weather key"
            w = d["weather"]
            if w is not None:
                for k in ["temperature_c", "aqi", "aqi_bucket", "sunrise", "before_sunrise"]:
                    assert k in w, f"run{i}: weather missing {k}"


# ---------- save persists weather ----------
class TestSaveWeatherPersistence:
    def _payload(self, d, name):
        return {
            "name": name,
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
            "weather": d["weather"],
        }

    def test_save_and_verify_weather_keys(self, api, repeat_runs):
        d = repeat_runs[0].json()
        r = api.post(
            f"{BASE_URL}/api/routes/save",
            json=self._payload(d, "TEST_iter3_weather"),
            timeout=60,
        )
        assert r.status_code == 200, r.text[:400]
        saved_id = r.json()["id"]

        lr = api.get(f"{BASE_URL}/api/routes/saved", timeout=30)
        assert lr.status_code == 200
        match = [x for x in lr.json()["routes"] if x["id"] == saved_id]
        assert match, "saved route missing from GET /api/routes/saved"
        got = match[0]
        assert "_id" not in got
        assert "weather" in got, "weather key dropped on save"
        w = got["weather"]
        assert w is not None, "weather persisted as null"
        for k in ["temperature_c", "aqi", "sunrise"]:
            assert k in w, f"saved weather missing key {k}"
        assert w.get("aqi_bucket") == d["weather"]["aqi_bucket"]

    def test_save_without_weather_still_ok(self, api, repeat_runs):
        d = repeat_runs[0].json()
        payload = self._payload(d, "TEST_iter3_noweather")
        payload.pop("weather")
        r = api.post(f"{BASE_URL}/api/routes/save", json=payload, timeout=60)
        assert r.status_code == 200, r.text[:400]
        saved_id = r.json()["id"]
        lr = api.get(f"{BASE_URL}/api/routes/saved", timeout=30)
        got = [x for x in lr.json()["routes"] if x["id"] == saved_id][0]
        assert "weather" in got and got["weather"] is None


# ---------- Delhi regression ----------
class TestDelhiRegression:
    def test_delhi_bounds_and_aqi(self, api):
        payload = dict(
            BLR_PAYLOAD,
            start_name="Connaught Place, Delhi",
            start_lon=77.209,
            start_lat=28.6139,
        )
        r = api.post(f"{BASE_URL}/api/routes/generate", json=payload, timeout=GEN_TIMEOUT)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["start"] == [77.209, 28.6139]
        assert 28.0 <= d["coordinates"][0][1] <= 29.0
        for lon, lat in d["coordinates"]:
            assert 28.0 <= lat <= 29.0, f"lat out of Delhi bounds: {lat}"
            assert 76.0 <= lon <= 78.0, f"lon out of Delhi bounds: {lon}"
        w = d["weather"]
        assert w is not None, "Delhi weather null"
        assert w["aqi"] is not None, "Delhi AQI null"
        assert w["aqi_bucket"] != "unknown"
