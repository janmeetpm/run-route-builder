"""Iteration 5 backend tests: digest preview/subscribe, friend_overlap gating, regressions."""
import os

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- /api/digest/preview ----------
class TestDigestPreview:
    @pytest.mark.parametrize("city", ["bengaluru", "delhi"])
    def test_preview_ok(self, client, city):
        r = client.get(f"{API}/digest/preview", params={"city": city, "distance_km": 5}, timeout=30)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d["city"] == city
        assert isinstance(d["week_of"], str) and len(d["week_of"]) > 0
        assert d["target_distance_km"] == 5
        picks = d["picks"]
        assert 4 <= len(picks) <= 5, f"expected 4-5 picks, got {len(picks)}"
        for p in picks:
            for k in ("digest_score", "blurb", "name", "distance_km", "athletes_this_week"):
                assert k in p, f"missing {k} in pick {p.get('name')}"
            assert isinstance(p["digest_score"], (int, float))
            assert isinstance(p["blurb"], str) and p["blurb"]
        scores = [p["digest_score"] for p in picks]
        assert scores == sorted(scores, reverse=True), "picks not sorted by digest_score"

    def test_preview_unknown_city_404(self, client):
        r = client.get(f"{API}/digest/preview", params={"city": "atlantis"}, timeout=30)
        assert r.status_code == 404, r.text[:300]

    def test_preview_defaults(self, client):
        r = client.get(f"{API}/digest/preview", timeout=30)
        assert r.status_code == 200
        assert r.json()["city"] == "bengaluru"

    def test_preview_distance_changes_ranking_scores(self, client):
        a = client.get(f"{API}/digest/preview", params={"city": "bengaluru", "distance_km": 3}, timeout=30).json()
        b = client.get(f"{API}/digest/preview", params={"city": "bengaluru", "distance_km": 15}, timeout=30).json()
        assert [p["name"] for p in a["picks"]] != [p["name"] for p in b["picks"]] or \
               [p["digest_score"] for p in a["picks"]] != [p["digest_score"] for p in b["picks"]]


# ---------- /api/digest/subscribe ----------
class TestDigestSubscribe:
    EMAIL = "TEST_digest_qa@example.test"

    def test_subscribe_ok(self, client):
        r = client.post(f"{API}/digest/subscribe",
                        json={"email": self.EMAIL, "city": "bengaluru", "distance_km": 5}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d == {"subscribed": True, "email": self.EMAIL}

    def test_subscribe_duplicate_upserts(self, client):
        for _ in range(2):
            r = client.post(f"{API}/digest/subscribe",
                            json={"email": self.EMAIL, "city": "delhi", "distance_km": 10}, timeout=30)
            assert r.status_code == 200, r.text[:300]
            assert r.json()["subscribed"] is True

    def test_subscribe_invalid_schema_422(self, client):
        r = client.post(f"{API}/digest/subscribe", json={"city": "bengaluru"}, timeout=30)
        assert r.status_code == 422, r.text[:300]

    def test_subscribe_bad_email_format(self, client):
        """Documented behaviour check: backend has no email validation (str type)."""
        r = client.post(f"{API}/digest/subscribe", json={"email": "not-an-email"}, timeout=30)
        assert r.status_code in (200, 422), r.text[:300]
        if r.status_code == 200:
            pytest.xfail("Backend accepts malformed email (no EmailStr validation)")


# ---------- /api/routes/friend_overlap gating ----------
class TestFriendOverlapGating:
    def test_no_oauth_401(self, client):
        r = client.post(f"{API}/routes/friend_overlap",
                        json={"coordinates": [[77.59, 12.97], [77.60, 12.98]]}, timeout=30)
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text[:300]}"

    def test_invalid_body_422(self, client):
        r = client.post(f"{API}/routes/friend_overlap", json={}, timeout=30)
        assert r.status_code in (401, 422)


# ---------- regressions ----------
class TestRegressions:
    def test_root(self, client):
        r = client.get(f"{API}/", timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    @pytest.mark.parametrize("city", ["bengaluru", "delhi"])
    def test_discovery(self, client, city):
        r = client.get(f"{API}/discovery", params={"city": city}, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["city"] == city
        assert len(d["routes"]) >= 4
        for rt in d["routes"]:
            for k in ("id", "name", "distance_km", "vibe", "difficulty", "athletes_this_week", "start"):
                assert k in rt

    def test_strava_status_disconnected(self, client):
        r = requests.get(f"{API}/strava/status", timeout=30)
        assert r.status_code == 200
        assert r.json() == {"connected": False}

    def test_generate_route(self, client):
        payload = {
            "start_name": "Cubbon Park",
            "start_lon": 77.5946,
            "start_lat": 12.9762,
            "distance_km": 5,
            "pace_group": "easy",
            "provider": "claude",
            "seed": 7,
        }
        r = client.post(f"{API}/routes/generate", json=payload, timeout=180)
        assert r.status_code == 200, r.text[:500]
        d = r.json()
        for k in ("id", "distance_km", "coordinates", "elevations", "cumulative_distance_m",
                  "steps", "midpoint", "narration", "llm_guess", "failure_log", "weather", "elev_stats"):
            assert k in d, f"missing {k}"
        assert len(d["coordinates"]) > 10
        assert len(d["coordinates"]) == len(d["elevations"]) == len(d["cumulative_distance_m"])
        assert d["narration"].get("headline")
        assert "_parse_ok" not in d["narration"]
        assert len(d["failure_log"]) >= 2
        pytest.route_cache = d

    def test_gpx_from_generated(self, client):
        d = getattr(pytest, "route_cache", None)
        if not d:
            pytest.skip("generate test did not run")
        r = client.post(f"{API}/routes/gpx",
                        json={"name": "TEST_route", "coordinates": d["coordinates"], "elevations": d["elevations"]},
                        timeout=60)
        assert r.status_code == 200
        assert "<gpx" in r.text and "<trkpt" in r.text

    def test_save_and_list(self, client):
        d = getattr(pytest, "route_cache", None)
        if not d:
            pytest.skip("generate test did not run")
        r = client.post(f"{API}/routes/save", json={
            "name": "TEST_saved_route",
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
        }, timeout=60)
        assert r.status_code == 200, r.text[:300]
        rid = r.json()["id"]
        lst = client.get(f"{API}/routes/saved", timeout=30)
        assert lst.status_code == 200
        routes = lst.json()["routes"]
        assert any(x["id"] == rid for x in routes)
        assert all("_id" not in x for x in routes), "MongoDB _id leaked"
