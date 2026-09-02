"""Iteration 6 tests: route accuracy retry, Strava-popularity routing, 8 narrator providers."""
import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

BLR = {"start_name": "MG Road, Bengaluru", "start_lon": 77.5946, "start_lat": 12.9716}
TIMEOUT = 180


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _gen(client, **kw):
    payload = dict(BLR, distance_km=8, provider="claude-haiku")
    payload.update(kw)
    return client.post(f"{BASE_URL}/api/routes/generate", json=payload, timeout=TIMEOUT)


# ---------- Module: retry_stats on /api/routes/generate ----------
class TestRetryStats:
    results = []

    @pytest.mark.parametrize("run", [1, 2, 3])
    def test_retry_stats_shape(self, client, run):
        r = _gen(client)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        rs = d.get("retry_stats")
        assert rs, "retry_stats missing"
        assert isinstance(rs.get("attempts"), list) and len(rs["attempts"]) >= 1
        for a in rs["attempts"]:
            for k in ("attempt", "seed", "requested_km", "actual_km", "err_pct"):
                assert k in a, f"attempt missing {k}: {a}"
        assert "final_err_pct" in rs and "converged" in rs
        assert rs["tolerance_pct"] == 15
        assert isinstance(rs["converged"], bool)
        # basic route sanity
        assert len(d["coordinates"]) > 10
        assert len(d["elevations"]) == len(d["coordinates"])
        TestRetryStats.results.append((rs["converged"], rs["final_err_pct"]))
        print(f"run{run}: converged={rs['converged']} final_err={rs['final_err_pct']} attempts={len(rs['attempts'])}")

    def test_at_least_two_of_three_converged(self, client):
        assert len(TestRetryStats.results) == 3, "prior runs did not complete"
        conv = [c for c, e in TestRetryStats.results if c and e <= 15]
        assert len(conv) >= 2, f"only {len(conv)}/3 converged: {TestRetryStats.results}"

    def test_failure_log_has_ors_retry_entries(self, client):
        r = _gen(client, distance_km=6)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        rs = d["retry_stats"]
        retry_entries = [e for e in d["failure_log"] if e.get("stage") == "ors_retry"]
        # one per attempt + one summary
        assert len(retry_entries) == len(rs["attempts"]) + 1, retry_entries
        for a, e in zip(rs["attempts"], retry_entries[:-1]):
            assert f"attempt {a['attempt']}" in e["message"]
            expected = "info" if a["err_pct"] is None or a["err_pct"] <= 15 else "warn"
            assert e["level"] == expected, f"{e} vs {a}"
        summary = retry_entries[-1]["message"]
        assert summary.startswith("Converged to") or summary.startswith("Best-of-"), summary


# ---------- Module: /api/routes/generate_from_strava ----------
class TestStravaPopularRouting:
    def test_requires_strava_session(self, client):
        r = client.post(f"{BASE_URL}/api/routes/generate_from_strava",
                        json=dict(BLR, distance_km=5), timeout=60)
        assert r.status_code == 401, f"{r.status_code} {r.text[:300]}"
        assert "Connect Strava" in r.text

    def test_bad_cookie_also_401(self, client):
        r = requests.post(f"{BASE_URL}/api/routes/generate_from_strava",
                          json=dict(BLR, distance_km=5),
                          cookies={"trailscribe_sid": "garbage.sig"}, timeout=60)
        assert r.status_code == 401, r.text[:300]


# ---------- Module: 8 narrator providers ----------
PROVIDERS = ["claude", "claude-haiku", "gemini", "gemini-flash",
             "gemini-lite", "gpt-terra", "gpt-luna", "gpt-mini"]


class TestProviders:
    @pytest.mark.parametrize("provider", PROVIDERS)
    def test_provider_generates_route(self, client, provider):
        r = _gen(client, provider=provider, distance_km=5)
        assert r.status_code == 200, f"{provider}: {r.status_code} {r.text[:400]}"
        d = r.json()
        assert d["provider"] == provider
        assert len(d["coordinates"]) > 10, provider
        assert len(d["elevations"]) == len(d["coordinates"])
        assert d["failure_log"], provider
        assert isinstance(d["narration"], dict)
        assert d["narration"].get("headline"), f"{provider} narration missing headline"
        narr_log = [e for e in d["failure_log"] if e["stage"] == "llm_narration"]
        print(f"{provider}: dist={d['distance_km']} narration_log={narr_log}")


# ---------- Module: regressions ----------
class TestRegressions:
    def test_gpx(self, client):
        r = client.post(f"{BASE_URL}/api/routes/gpx", json={
            "name": "TEST_route", "coordinates": [[77.59, 12.97], [77.60, 12.98]],
            "elevations": [900.0, 910.0],
        }, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert "<gpx" in r.text and "77.59" in r.text
        assert "gpx" in r.headers.get("content-type", "")

    def test_gpx_empty_coords(self, client):
        r = client.post(f"{BASE_URL}/api/routes/gpx", json={"name": "x", "coordinates": []}, timeout=30)
        assert r.status_code == 422

    def test_digest_preview(self, client):
        r = client.get(f"{BASE_URL}/api/digest/preview", params={"city": "bengaluru", "distance_km": 5}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["city"] == "bengaluru"
        assert 1 <= len(d["picks"]) <= 5
        assert all("blurb" in p and "digest_score" in p for p in d["picks"])
        scores = [p["digest_score"] for p in d["picks"]]
        assert scores == sorted(scores, reverse=True)

    def test_digest_preview_bad_city(self, client):
        r = client.get(f"{BASE_URL}/api/digest/preview", params={"city": "atlantis"}, timeout=30)
        assert r.status_code == 404

    def test_digest_subscribe(self, client):
        email = "TEST_it6@example.com"
        r = client.post(f"{BASE_URL}/api/digest/subscribe",
                        json={"email": email, "city": "delhi", "distance_km": 7}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json() == {"subscribed": True, "email": email}

    def test_digest_subscribe_invalid_email(self, client):
        r = client.post(f"{BASE_URL}/api/digest/subscribe", json={"email": "notanemail"}, timeout=30)
        assert r.status_code == 422

    def test_strava_status(self, client):
        r = client.get(f"{BASE_URL}/api/strava/status", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["connected"] is False

    def test_discovery(self, client):
        r = client.get(f"{BASE_URL}/api/discovery", params={"city": "bengaluru"}, timeout=30)
        assert r.status_code == 200
        assert len(r.json()["routes"]) > 0
