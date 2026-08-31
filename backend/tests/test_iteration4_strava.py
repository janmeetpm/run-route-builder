"""Iteration 4: Strava OAuth surfaces, 401 gates, GPX export, regressions."""
import os
import re
from urllib.parse import urlparse, parse_qs

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

EXPECTED_SCOPE = "read,activity:read,activity:read_all,profile:read_all"


@pytest.fixture
def client():
    s = requests.Session()
    return s


# ---------- /api/strava/status ----------
class TestStravaStatus:
    def test_status_no_cookie(self, client):
        r = client.get(f"{API}/strava/status", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("connected") is False, data


# ---------- /api/strava/authorize ----------
class TestStravaAuthorize:
    def test_authorize_redirect(self, client):
        r = client.get(f"{API}/strava/authorize", allow_redirects=False, timeout=30)
        assert r.status_code == 307, f"expected 307, got {r.status_code}: {r.text[:300]}"
        loc = r.headers.get("location", "")
        assert loc.startswith("https://www.strava.com/oauth/authorize"), loc
        q = parse_qs(urlparse(loc).query)
        assert q.get("client_id") == ["276007"], q.get("client_id")
        assert q.get("response_type") == ["code"]
        assert q.get("scope") == [EXPECTED_SCOPE], q.get("scope")
        assert q.get("redirect_uri") == [
            "https://route-fail-learn.preview.emergentagent.com/api/strava/callback"
        ], q.get("redirect_uri")
        assert q.get("state") and len(q["state"][0]) > 10, q.get("state")

        # HttpOnly session cookie set
        set_cookie = r.headers.get("set-cookie", "")
        assert "trailscribe_sid" in set_cookie, set_cookie
        assert "HttpOnly" in set_cookie, set_cookie
        assert "Secure" in set_cookie, set_cookie

    def test_authorize_reuses_cookie_session(self, client):
        r1 = client.get(f"{API}/strava/authorize", allow_redirects=False, timeout=30)
        assert r1.status_code == 307
        sid1 = client.cookies.get("trailscribe_sid")
        assert sid1
        r2 = client.get(f"{API}/strava/authorize", allow_redirects=False, timeout=30)
        assert r2.status_code == 307
        sid2 = client.cookies.get("trailscribe_sid")
        assert sid2 == sid1, "session id should be reused when cookie present"
        # states must differ per call
        s1 = parse_qs(urlparse(r1.headers["location"]).query)["state"][0]
        s2 = parse_qs(urlparse(r2.headers["location"]).query)["state"][0]
        assert s1 != s2


# ---------- /api/strava/callback ----------
class TestStravaCallback:
    def test_callback_missing_code_and_state(self, client):
        r = client.get(f"{API}/strava/callback", allow_redirects=False, timeout=30)
        assert r.status_code == 400, f"{r.status_code}: {r.text[:300]}"
        assert "code" in r.text.lower()

    def test_callback_missing_code_only(self, client):
        r = client.get(f"{API}/strava/callback", params={"state": "abc"},
                       allow_redirects=False, timeout=30)
        assert r.status_code == 400, r.text[:300]

    def test_callback_tampered_state(self, client):
        # establish a session + stored state
        a = client.get(f"{API}/strava/authorize", allow_redirects=False, timeout=30)
        assert a.status_code == 307
        assert client.cookies.get("trailscribe_sid")
        r = client.get(
            f"{API}/strava/callback",
            params={"code": "fakecode", "state": "TAMPERED_STATE_VALUE"},
            allow_redirects=False, timeout=30,
        )
        assert r.status_code == 400, f"{r.status_code}: {r.text[:300]}"
        assert "Invalid or expired OAuth state" in r.text, r.text[:300]

    def test_callback_error_param_redirects(self, client):
        r = client.get(f"{API}/strava/callback", params={"error": "access_denied"},
                       allow_redirects=False, timeout=30)
        assert r.status_code == 303, f"{r.status_code}: {r.text[:300]}"
        assert "strava=error" in r.headers.get("location", "")


# ---------- 401 gates on protected endpoints ----------
class TestProtectedEndpoints401:
    def test_city_segments_requires_auth(self, client):
        r = client.get(f"{API}/strava/city_segments", params={"city": "bengaluru"}, timeout=40)
        assert r.status_code == 401, f"{r.status_code}: {r.text[:300]}"

    def test_activities_requires_auth(self, client):
        r = client.get(f"{API}/strava/activities", timeout=30)
        assert r.status_code == 401, f"{r.status_code}: {r.text[:300]}"

    def test_rank_by_strava_requires_auth(self, client):
        r = client.post(f"{API}/routes/rank_by_strava",
                        json={"coordinates": [[77.59, 12.97], [77.60, 12.98]],
                              "activity_type": "running"}, timeout=40)
        assert r.status_code == 401, f"{r.status_code}: {r.text[:300]}"

    def test_gates_hold_with_state_only_session(self, client):
        """A session created by /authorize (no token) must still 401."""
        client.get(f"{API}/strava/authorize", allow_redirects=False, timeout=30)
        assert client.cookies.get("trailscribe_sid")
        r = client.get(f"{API}/strava/activities", timeout=30)
        assert r.status_code == 401, f"{r.status_code}: {r.text[:300]}"
        r2 = client.post(f"{API}/routes/rank_by_strava",
                         json={"coordinates": [[77.59, 12.97], [77.60, 12.98]]}, timeout=40)
        assert r2.status_code == 401, f"{r2.status_code}: {r2.text[:300]}"
        st = client.get(f"{API}/strava/status", timeout=30)
        assert st.status_code == 200 and st.json().get("connected") is False


# ---------- /api/strava/logout ----------
class TestStravaLogout:
    def test_logout_idempotent_without_session(self, client):
        r = client.post(f"{API}/strava/logout", timeout=30)
        assert r.status_code == 200, r.text[:300]

    def test_logout_clears_cookie(self, client):
        client.get(f"{API}/strava/authorize", allow_redirects=False, timeout=30)
        r = client.post(f"{API}/strava/logout", timeout=30)
        assert r.status_code == 200
        assert "trailscribe_sid" in r.headers.get("set-cookie", "").lower()


# ---------- /api/routes/gpx ----------
class TestGpxExport:
    COORDS = [[77.5946, 12.9716], [77.5950, 12.9720], [77.5960, 12.9730]]

    def test_gpx_basic(self, client):
        r = client.post(f"{API}/routes/gpx",
                        json={"name": "TEST_Cubbon Loop", "coordinates": self.COORDS},
                        timeout=30)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        assert "application/gpx+xml" in r.headers.get("content-type", ""), r.headers
        cd = r.headers.get("content-disposition", "")
        assert cd.startswith("attachment"), cd
        assert ".gpx" in cd, cd
        body = r.text
        assert "<gpx" in body
        assert 'version="1.1"' in body
        assert body.count("<trkpt lat=") == len(self.COORDS), body[:500]
        assert '<trkpt lat="12.9716" lon="77.5946"' in body, body[:600]
        assert "<ele>" not in body

    def test_gpx_with_elevations(self, client):
        r = client.post(f"{API}/routes/gpx",
                        json={"name": "TEST_Elev", "coordinates": self.COORDS,
                              "elevations": [900.0, 905.5, 910.25]},
                        timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.text
        assert body.count("<ele>") == 3, body[:600]
        assert "<ele>900.0</ele>" in body
        assert "<ele>905.5</ele>" in body
        assert "<ele>910.2</ele>" in body or "<ele>910.3</ele>" in body

    def test_gpx_default_name(self, client):
        r = client.post(f"{API}/routes/gpx", json={"coordinates": self.COORDS}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert "Trailscribe route" in r.text

    def test_gpx_xml_escaping(self, client):
        r = client.post(f"{API}/routes/gpx",
                        json={"name": 'TEST_<bad> & "quote"', "coordinates": self.COORDS},
                        timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert "&lt;bad&gt;" in r.text and "&amp;" in r.text
        assert "<bad>" not in r.text

    def test_gpx_missing_coordinates_validation(self, client):
        r = client.post(f"{API}/routes/gpx", json={"name": "TEST_x"}, timeout=30)
        assert r.status_code == 422, f"{r.status_code}: {r.text[:300]}"

    def test_gpx_empty_coordinates(self, client):
        r = client.post(f"{API}/routes/gpx", json={"coordinates": []}, timeout=30)
        # Should not 500
        assert r.status_code in (200, 400, 422), f"{r.status_code}: {r.text[:300]}"


# ---------- Regressions ----------
class TestRegressions:
    @pytest.mark.parametrize("city", ["bengaluru", "delhi"])
    def test_discovery(self, client, city):
        r = client.get(f"{API}/discovery", params={"city": city}, timeout=60)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        data = r.json()
        assert "routes" in data and isinstance(data["routes"], list) and data["routes"]
        first = data["routes"][0]
        assert "_id" not in str(data)
        assert first.get("name")

    def test_route_generate(self, client):
        payload = {
            "start_name": "Cubbon Park, Bengaluru",
            "start_lon": 77.5946,
            "start_lat": 12.9716,
            "distance_km": 5,
            "pace_group": "easy",
            "provider": "claude",
        }
        r = client.post(f"{API}/routes/generate", json=payload, timeout=180)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:500]}"
        data = r.json()
        assert data.get("coordinates") and len(data["coordinates"]) > 10
        assert isinstance(data.get("failure_log"), list)
        assert data.get("distance_km")
        assert "_id" not in data
        # feed generated route into GPX
        g = client.post(f"{API}/routes/gpx",
                        json={"name": "TEST_Generated", "coordinates": data["coordinates"],
                              "elevations": data.get("elevations")}, timeout=60)
        assert g.status_code == 200, g.text[:300]
        assert re.search(r'<trkpt lat="[-\d.]+" lon="[-\d.]+"', g.text)

    def test_saved_routes_list(self, client):
        r = client.get(f"{API}/routes/saved", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(r.json().get("routes"), list)
        assert "_id" not in r.text
