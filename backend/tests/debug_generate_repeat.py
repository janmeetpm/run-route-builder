"""Repeat POST /api/routes/generate to measure narration-fallback frequency (RCA harness)."""
import os
import json
import requests
from dotenv import dotenv_values

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]).rstrip("/")

PAYLOAD = {
    "start_name": "Cubbon Park Gate 4, Bengaluru",
    "start_lon": 77.5946, "start_lat": 12.9762, "distance_km": 5,
    "pace_group": "easy", "provider": "claude",
    "constraints": {"loop": True, "water_stop": True, "avoid_highways": True, "well_lit": True, "start_time": "05:30"},
}

FALLBACK = "Route narration unavailable"

for i in range(3):
    for prov in ["claude", "gemini"]:
        p = dict(PAYLOAD, provider=prov)
        r = requests.post(f"{BASE}/api/routes/generate", json=p, timeout=180)
        if r.status_code != 200:
            print(f"run{i} {prov}: HTTP {r.status_code} {r.text[:200]}")
            continue
        d = r.json()
        n = d["narration"]["narration"]
        w = d.get("weather")
        print(f"run{i} {prov}: narration_len={len(n)} fallback={FALLBACK in n} "
              f"weather_sunrise={(w or {}).get('sunrise')} aqi={(w or {}).get('aqi')} temp={(w or {}).get('temperature_c')} "
              f"steps={len(d['steps'])}")
        if FALLBACK in n:
            print("   failure_log:", json.dumps([e for e in d["failure_log"] if e["stage"] in ("llm_narration", "weather")], indent=1)[:600])
