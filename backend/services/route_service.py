"""OpenRouteService integration — real routing geometry for loop routes.

Rationale: LLMs are bad at geometry. This module handles the actual route
construction so we can compare LLM guesses against ground truth. Includes
an accuracy-retry loop when ORS overshoots the requested distance.
"""
import os
import re
import math
import random
import httpx
from typing import List, Dict, Optional, Tuple


ORS_BASE = "https://api.openrouteservice.org/v2/directions/foot-walking"
ORS_GEOJSON = ORS_BASE + "/geojson"
ORS_SNAP = "https://api.openrouteservice.org/v2/snap/foot-walking/json"

# ORS reports an unroutable waypoint as e.g. "...of specified coordinate 3: 77.6 12.9"
_UNROUTABLE_COORD_RE = re.compile(r"coordinate\s+(\d+)", re.IGNORECASE)

# Public-API foot-walking snapping radius. Strava segment endpoints come from
# GPS traces and routinely sit 10-40 m off the walkable network.
SNAP_RADIUS_M = 350
MAX_WAYPOINT_RETRIES = 5

DEFAULT_TOLERANCE = 0.15   # 15% deviation from target ok
MAX_ATTEMPTS = 4


async def _post_ors(body: Dict) -> Dict:
    api_key = os.environ["ORS_API_KEY"]
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json, application/geo+json",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(ORS_GEOJSON, json=body, headers=headers)
        if r.status_code != 200:
            raise RuntimeError(f"ORS error {r.status_code}: {r.text[:250]}")
        return r.json()


def _shape_route(data: Dict) -> Dict:
    feature = data["features"][0]
    coords = feature["geometry"]["coordinates"]
    summary = feature["properties"]["summary"]
    segments = feature["properties"].get("segments", [])
    elevations = [c[2] if len(c) > 2 else 0.0 for c in coords]
    coords_2d = [[c[0], c[1]] for c in coords]
    dists = [0.0]
    for i in range(1, len(coords_2d)):
        dists.append(dists[-1] + _haversine_m(coords_2d[i - 1], coords_2d[i]))
    steps: List[Dict] = []
    for seg in segments:
        for step in seg.get("steps", []):
            steps.append({
                "instruction": step.get("instruction"),
                "distance_m": step.get("distance"),
                "duration_s": step.get("duration"),
                "type": step.get("type"),
            })
    mid_idx = len(coords_2d) // 2
    return {
        "coordinates": coords_2d,
        "elevations": elevations,
        "cumulative_distance_m": dists,
        "distance_m": summary.get("distance", 0.0),
        "duration_s": summary.get("duration", 0.0),
        "steps": steps,
        "midpoint": coords_2d[mid_idx],
        "start": coords_2d[0],
        "end": coords_2d[-1],
        "closed": _haversine_m(coords_2d[0], coords_2d[-1]) < 30.0,
    }


async def _one_loop(lon: float, lat: float, target_km: float, seed: int) -> Dict:
    body = {
        "coordinates": [[lon, lat]],
        "options": {
            "round_trip": {"length": int(target_km * 1000), "points": 5, "seed": seed}
        },
        "elevation": True,
        "instructions": True,
        "geometry": True,
    }
    return _shape_route(await _post_ors(body))


async def generate_loop_route(
    lon: float,
    lat: float,
    distance_km: float,
    avoid_highways: bool = True,
    seed: Optional[int] = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> Dict:
    """Real closed-loop walking route with accuracy retry.

    Strategy:
    - Try up to MAX_ATTEMPTS attempts. Each attempt varies the seed and
      corrects the requested `length` by the inverse of the previous
      attempt's overshoot ratio.
    - Return the best (lowest error) attempt; attach a `retry_stats` field
      recording every attempt so the failure log can show how ORS was
      pushed until it converged.
    """
    attempts: List[Dict] = []
    best: Optional[Dict] = None
    best_err = float("inf")
    request_km = float(distance_km)

    for i in range(MAX_ATTEMPTS):
        seed_use = seed if (i == 0 and seed is not None) else random.randint(1, 99999)
        try:
            route = await _one_loop(lon, lat, request_km, seed_use)
        except Exception as e:
            attempts.append({
                "attempt": i + 1, "seed": seed_use,
                "requested_km": round(request_km, 2), "actual_km": None,
                "err_pct": None, "error": str(e)[:120],
            })
            continue

        actual_km = route["distance_m"] / 1000
        err = abs(actual_km - distance_km) / max(distance_km, 0.01)
        attempts.append({
            "attempt": i + 1, "seed": seed_use,
            "requested_km": round(request_km, 2),
            "actual_km": round(actual_km, 2),
            "err_pct": round(err * 100, 1),
        })
        if err < best_err:
            best_err = err
            best = route
        if err <= tolerance:
            break
        # Correct next attempt: if we overshot, ask for proportionally less
        ratio = distance_km / max(actual_km, 0.01)
        request_km = max(1.0, min(30.0, request_km * ratio))

    if best is None:
        raise RuntimeError("All ORS attempts failed")
    best["retry_stats"] = {
        "attempts": attempts,
        "final_err_pct": round(best_err * 100, 1),
        "converged": best_err <= tolerance,
        "tolerance_pct": int(tolerance * 100),
    }
    return best


async def _snap_to_network(
    coordinates: List[List[float]], radius_m: int = SNAP_RADIUS_M
) -> Optional[List[Optional[List[float]]]]:
    """Best-effort snap of raw GPS points onto the foot-walking network.

    Returns one entry per input coordinate — the snapped [lon, lat], or None
    where ORS found nothing routable in range. Returns None entirely if the
    snap endpoint is unavailable, so callers treat snapping as optional.
    """
    api_key = os.environ["ORS_API_KEY"]
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {"locations": coordinates, "radius": radius_m}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(ORS_SNAP, json=body, headers=headers)
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception:
        return None

    locations = data.get("locations")
    if not isinstance(locations, list) or len(locations) != len(coordinates):
        return None

    out: List[Optional[List[float]]] = []
    for entry in locations:
        if isinstance(entry, dict) and isinstance(entry.get("location"), list):
            loc = entry["location"]
            if len(loc) >= 2:
                out.append([float(loc[0]), float(loc[1])])
                continue
        out.append(None)
    return out


def _dedupe_consecutive(
    coordinates: List[List[float]], min_gap_m: float = 25.0
) -> List[List[float]]:
    """Drop waypoints that sit on top of their predecessor.

    Adjacent Strava segments often share an endpoint; ORS rejects a leg whose
    source and target are the same point. The final coordinate is always kept
    so a closed loop stays closed.
    """
    if len(coordinates) <= 2:
        return list(coordinates)
    kept = [coordinates[0]]
    for c in coordinates[1:-1]:
        if _haversine_m(kept[-1], c) >= min_gap_m:
            kept.append(c)
    kept.append(coordinates[-1])
    return kept


async def generate_waypoint_route(
    coordinates: List[List[float]],
) -> Dict:
    """Real foot-walking route through explicit waypoints (used for Strava-
    popularity routing). `coordinates` is [[lon,lat], ...] with the same
    point at the start and end for a closed loop.

    Strava segment endpoints are raw GPS and frequently aren't routable for
    foot-walking. A single bad waypoint 400s the whole ORS request, so we
    snap first, then drop individual offending waypoints and retry rather
    than losing the route. The start/end anchor is never dropped.
    """
    requested = len(coordinates)
    coords = _dedupe_consecutive(coordinates)

    snapped = await _snap_to_network(coords)
    if snapped:
        rebuilt: List[List[float]] = []
        for i, (original, snap) in enumerate(zip(coords, snapped)):
            is_anchor = i == 0 or i == len(coords) - 1
            if snap:
                rebuilt.append(snap)
            elif is_anchor:
                # Keep the runner's own start point even if snapping failed.
                rebuilt.append(original)
            # else: unsnappable intermediate waypoint — leave it out.
        # Re-close the loop if the anchors both snapped to slightly different points.
        coords = _dedupe_consecutive(rebuilt)

    dropped_unroutable: List[int] = []
    last_error: Optional[Exception] = None

    for _ in range(MAX_WAYPOINT_RETRIES):
        if len(coords) < 2:
            break
        body = {
            "coordinates": coords,
            "elevation": True,
            "instructions": True,
            "geometry": True,
        }
        try:
            shaped = _shape_route(await _post_ors(body))
        except RuntimeError as e:
            last_error = e
            idx = _unroutable_index(str(e), len(coords))
            if idx is None:
                raise
            dropped_unroutable.append(idx)
            coords = coords[:idx] + coords[idx + 1:]
            continue

        shaped["waypoints_requested"] = requested
        shaped["waypoints_used"] = len(coords)
        shaped["waypoints_dropped"] = requested - len(coords)
        return shaped

    raise RuntimeError(
        f"ORS could not route the Strava waypoints after dropping "
        f"{len(dropped_unroutable)} unroutable point(s): {last_error}"
    )


def _unroutable_index(message: str, n_coords: int) -> Optional[int]:
    """Pull the offending waypoint index out of an ORS error message.

    Returns None when the error isn't an unroutable-point complaint, or when
    the culprit is the start/end anchor — in both cases dropping a waypoint
    won't help and the caller should fall back instead.
    """
    if "routable point" not in message.lower():
        return None
    m = _UNROUTABLE_COORD_RE.search(message)
    if not m:
        return None
    idx = int(m.group(1))
    if idx <= 0 or idx >= n_coords - 1:
        return None
    return idx


def _haversine_m(a: List[float], b: List[float]) -> float:
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
