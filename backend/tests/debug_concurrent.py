"""Two concurrent /api/routes/generate calls — reproduce the non-JSON gateway error seen under xdist."""
import os
import concurrent.futures as cf
import requests
from dotenv import dotenv_values

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]).rstrip("/")
P = {
    "start_name": "Cubbon Park Gate 4, Bengaluru",
    "start_lon": 77.5946, "start_lat": 12.9762, "distance_km": 5,
    "pace_group": "easy", "provider": "claude",
    "constraints": {"loop": True, "water_stop": True, "avoid_highways": True, "well_lit": True, "start_time": "05:30"},
}


def call(prov):
    r = requests.post(f"{BASE}/api/routes/generate", json=dict(P, provider=prov), timeout=180)
    ct = r.headers.get("content-type")
    return prov, r.status_code, ct, r.text[:200].replace("\n", " ")


with cf.ThreadPoolExecutor(4) as ex:
    for res in ex.map(call, ["claude", "gemini", "claude", "gemini"]):
        print(res)
