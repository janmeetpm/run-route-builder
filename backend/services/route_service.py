"""OpenRouteService integration — real routing geometry for loop routes.

Rationale: LLMs are bad at geometry. This module handles the actual route
construction so we can compare LLM guesses against ground truth.
"""
import os
import random
import httpx
from typing import List, Dict, Optional


ORS_BASE = "https://api.openrouteservice.org/v2/directions/foot-walking"


async def generate_loop_route(
    lon: float,
    lat: float,
    distance_km: float,
    avoid_highways: bool = True,
    seed: Optional[int] = None,
) -> Dict:
    """Ask OpenRouteService for a real closed-loop walking/running route.

    Returns GeoJSON-shaped dict with geometry, distance_m, duration_s, elevations.
    """
    api_key = os.environ["ORS_API_KEY"]
    if seed is None:
        seed = random.randint(1, 99999)

    body = {
        "coordinates": [[lon, lat]],
        "options": {
            "round_trip": {
                "length": int(distance_km * 1000),
                "points": 5,
                "seed": seed,
            }
        },
        "elevation": True,
        "instructions": True,
        "geometry": True,
    }
    if avoid_highways:
        # foot-walking profile doesn't support 'highways' avoid; skip silently.
        # (We still surface the constraint to the LLM narration.)
        pass

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json, application/geo+json",
    }

    url = ORS_BASE + "/geojson"
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=body, headers=headers)
        if r.status_code != 200:
            raise RuntimeError(f"ORS error {r.status_code}: {r.text[:300]}")
        data = r.json()

    feature = data["features"][0]
    coords = feature["geometry"]["coordinates"]  # [[lon, lat, ele], ...]
    summary = feature["properties"]["summary"]
    segments = feature["properties"].get("segments", [])

    # Build elevation series
    elevations = [c[2] if len(c) > 2 else 0.0 for c in coords]
    coords_2d = [[c[0], c[1]] for c in coords]

    # Cumulative distance along path (meters) for elevation chart
    dists = [0.0]
    for i in range(1, len(coords_2d)):
        dists.append(dists[-1] + _haversine_m(coords_2d[i - 1], coords_2d[i]))

    # Turn instructions
    steps: List[Dict] = []
    for seg in segments:
        for step in seg.get("steps", []):
            steps.append({
                "instruction": step.get("instruction"),
                "distance_m": step.get("distance"),
                "duration_s": step.get("duration"),
                "type": step.get("type"),
            })

    # Pick a midpoint for water stop
    mid_idx = len(coords_2d) // 2
    midpoint = coords_2d[mid_idx]

    return {
        "coordinates": coords_2d,
        "elevations": elevations,
        "cumulative_distance_m": dists,
        "distance_m": summary.get("distance", 0.0),
        "duration_s": summary.get("duration", 0.0),
        "steps": steps,
        "midpoint": midpoint,  # [lon, lat]
        "start": coords_2d[0],
        "end": coords_2d[-1],
        "closed": _haversine_m(coords_2d[0], coords_2d[-1]) < 30.0,  # closure check
    }


def _haversine_m(a: List[float], b: List[float]) -> float:
    import math
    lon1, lat1 = a
    lon2, lat2 = b
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    x = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(x))


def compute_elevation_stats(elevations: List[float]) -> Dict:
    """Compute total ascent, descent, min/max."""
    if not elevations:
        return {"ascent_m": 0, "descent_m": 0, "min_m": 0, "max_m": 0}
    ascent = 0.0
    descent = 0.0
    for i in range(1, len(elevations)):
        d = elevations[i] - elevations[i - 1]
        if d > 0:
            ascent += d
        else:
            descent += -d
    return {
        "ascent_m": round(ascent, 1),
        "descent_m": round(descent, 1),
        "min_m": round(min(elevations), 1),
        "max_m": round(max(elevations), 1),
    }
