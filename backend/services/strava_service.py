"""Strava API v3 integration: OAuth, segments, activities, and route→segment
overlap scoring for the 'safe & tested' route ranking.

Single-user session model (Emergent preview): OAuth session state and the
resulting token are stored in Mongo under a signed cookie's session id.
Tokens auto-refresh 60s before expiry.
"""
import os
import time
import asyncio
import math
import hashlib
import secrets
from typing import Dict, List, Optional, Tuple

import httpx
import polyline
from itsdangerous import URLSafeSerializer, BadSignature


STRAVA_OAUTH = "https://www.strava.com/oauth"
STRAVA_API = "https://www.strava.com/api/v3"
SCOPES = "read,activity:read,activity:read_all,profile:read_all"


def _client_id() -> str:
    return os.environ["STRAVA_CLIENT_ID"]


def _client_secret() -> str:
    return os.environ["STRAVA_CLIENT_SECRET"]


def _redirect_uri() -> str:
    return os.environ["STRAVA_REDIRECT_URI"]


def _signer() -> URLSafeSerializer:
    return URLSafeSerializer(os.environ["SESSION_SECRET"], salt="strava-session-v1")


def new_session_id() -> str:
    return secrets.token_urlsafe(24)


def sign_sid(sid: str) -> str:
    return _signer().dumps(sid)


def unsign_sid(cookie_value: str) -> Optional[str]:
    try:
        return _signer().loads(cookie_value)
    except BadSignature:
        return None


def build_authorize_url(state: str) -> str:
    from urllib.parse import urlencode

    params = {
        "client_id": _client_id(),
        "response_type": "code",
        "redirect_uri": _redirect_uri(),
        "approval_prompt": "auto",
        "scope": SCOPES,
        "state": state,
    }
    return f"{STRAVA_OAUTH}/authorize?{urlencode(params)}"


async def exchange_code(code: str) -> Dict:
    body = {
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{STRAVA_OAUTH}/token", data=body)
        r.raise_for_status()
        return r.json()


async def refresh_token(refresh: str) -> Dict:
    body = {
        "client_id": _client_id(),
        "client_secret": _client_secret(),
        "grant_type": "refresh_token",
        "refresh_token": refresh,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{STRAVA_OAUTH}/token", data=body)
        r.raise_for_status()
        return r.json()


async def valid_access_token(db, sid: str) -> Optional[str]:
    """Return a live access token for this session; refresh if expiring."""
    doc = await db.strava_sessions.find_one({"_id": sid})
    if not doc or not doc.get("refresh_token"):
        return None
    if doc.get("expires_at", 0) > int(time.time()) + 60:
        return doc["access_token"]
    try:
        tok = await refresh_token(doc["refresh_token"])
    except Exception:
        return None
    await db.strava_sessions.update_one(
        {"_id": sid},
        {"$set": {
            "access_token": tok["access_token"],
            "refresh_token": tok["refresh_token"],
            "expires_at": tok["expires_at"],
            "updated_at": time.time(),
        }},
    )
    return tok["access_token"]


async def strava_get(token: str, path: str, params: Optional[Dict] = None) -> Tuple[int, Dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{STRAVA_API}{path}", params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            data = r.json()
        except Exception:
            data = {"error": r.text[:200]}
        return r.status_code, data


# ---------------- Route ↔ segment overlap scoring ----------------

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


def _bbox(coords: List[List[float]]) -> Tuple[float, float, float, float]:
    """Return (south, west, north, east) for a list of [lon, lat]."""
    lats = [c[1] for c in coords]
    lons = [c[0] for c in coords]
    pad = 0.003  # ~330m
    return (min(lats) - pad, min(lons) - pad, max(lats) + pad, max(lons) + pad)


def _sample(coords: List[List[float]], n: int) -> List[List[float]]:
    if len(coords) <= n:
        return coords
    stride = max(1, len(coords) // n)
    return coords[::stride]


def _latlng_to_lonlat(value) -> Optional[List[float]]:
    """Convert Strava [lat, lon] values to ORS [lon, lat] coordinates."""
    if not isinstance(value, list) or len(value) < 2:
        return None
    try:
        lat = float(value[0])
        lon = float(value[1])
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return [lon, lat]


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def score_segment_overlap(
    route_coords: List[List[float]],  # [[lon, lat], ...]
    seg_points_lat_lon: List[Tuple[float, float]],
    max_dist_m: float = 40.0,
) -> float:
    """Fraction 0.0–1.0 of segment points within `max_dist_m` of the route.

    Cheap O(seg_pts * route_pts) — we downsample both sides first.
    """
    if not seg_points_lat_lon or not route_coords:
        return 0.0
    route_s = _sample(route_coords, 200)  # [lon,lat]
    seg_s = _sample(
        [[lon, lat] for (lat, lon) in seg_points_lat_lon], 80
    )
    inside = 0
    for p in seg_s:
        for q in route_s:
            if _haversine_m(p, q) <= max_dist_m:
                inside += 1
                break
    return inside / len(seg_s)


async def enrich_segment_stats(
    token: str, segs: List[Dict], limit: int = 10
) -> List[Dict]:
    """Fill in popularity counts that /segments/explore doesn't return.

    The explore endpoint's ExplorerSegment payload carries geometry and
    distance but no athlete_count/effort_count, so ranking "most-run"
    segments off an explore response sorts by zero. /segments/{id} has the
    real counts. Best-effort and mutates in place: on any failure (rate
    limit, deleted segment, private) the segment keeps a count of 0 rather
    than failing the request.
    """
    targets = [
        s for s in segs
        if s.get("id") is not None and not s.get("athlete_count")
    ][:limit]
    if not targets:
        return segs

    async def one(s: Dict):
        try:
            status, data = await strava_get(token, f"/segments/{s['id']}")
        except Exception:
            return
        if status >= 400 or not isinstance(data, dict):
            return
        s["athlete_count"] = int(_num(data.get("athlete_count")))
        s["effort_count"] = int(_num(data.get("effort_count")))
        s["star_count"] = int(_num(data.get("star_count")))

    await asyncio.gather(*(one(s) for s in targets), return_exceptions=True)
    return segs


async def pick_popular_segments_near(
    token: str,
    lon: float,
    lat: float,
    distance_km: float,
    activity_type: str = "running",
) -> Dict:
    """Return the top-athlete_count segments near a point, plus an ordered
    waypoint list you can hand to ORS to build a real loop through them.

    Strategy: query /segments/explore in a bbox scaled by the target loop
    distance, keep only segments whose midpoint is within the search
    radius, greedily pick the highest-athlete_count segments until their
    combined length is ~40-60% of the target (the connectors from ORS make
    up the rest), then order the picks nearest-neighbour from the start.
    """
    # bbox scaled by expected loop radius (~ distance_km / (2*pi) km)
    radius_km = max(0.6, min(3.0, distance_km / (2 * math.pi) + 0.4))
    d_lat = radius_km / 110.574
    d_lon = radius_km / (111.320 * max(0.2, math.cos(math.radians(lat))))
    bounds = f"{lat - d_lat},{lon - d_lon},{lat + d_lat},{lon + d_lon}"

    status, data = await strava_get(
        token, "/segments/explore",
        {"bounds": bounds, "activity_type": activity_type},
    )
    if status >= 400:
        return {"error": data, "segments": [], "waypoints": []}
    segs = data.get("segments", []) if isinstance(data, dict) else []
    segs = segs or []
    if not segs:
        return {"segments": [], "waypoints": [], "note": "no segments in area"}

    target_m = int(distance_km * 1000 * 0.55)  # 55% of loop budget from segments

    # Keep only segments we can actually thread a route through, before
    # spending API calls on popularity lookups.
    candidates: List[Dict] = []
    for s in segs:
        if not _latlng_to_lonlat(s.get("start_latlng")):
            continue
        if not _latlng_to_lonlat(s.get("end_latlng")):
            continue
        d = _num(s.get("distance"))
        if d < 100 or d > target_m:  # skip tiny/huge segments
            continue
        candidates.append(s)

    if not candidates:
        return {"segments": [], "waypoints": [], "note": "no suitable segments"}

    # explore() gives no counts — fetch them so "most-run" means something.
    await enrich_segment_stats(token, candidates)
    candidates.sort(
        key=lambda s: (
            _num(s.get("athlete_count")),
            _num(s.get("effort_count")),
            _num(s.get("distance")),
        ),
        reverse=True,
    )

    picked: List[Dict] = []
    running_m = 0.0
    for s in candidates:
        picked.append(s)
        running_m += _num(s.get("distance"))
        if running_m >= target_m or len(picked) >= 4:
            break

    # Order nearest-neighbour from the start point
    start = [lon, lat]
    remaining = list(picked)
    ordered: List[Dict] = []
    current = start
    while remaining:
        remaining.sort(key=lambda s: _haversine_m(current, _latlng_to_lonlat(s.get("start_latlng")) or start))
        nxt = remaining.pop(0)
        ordered.append(nxt)
        current = _latlng_to_lonlat(nxt.get("end_latlng")) or current

    # Build waypoints: start -> [segA_start, segA_end, segB_start, segB_end, ...] -> start
    waypoints: List[List[float]] = [start]
    picks_summary: List[Dict] = []
    for s in ordered:
        sl = _latlng_to_lonlat(s.get("start_latlng"))
        el = _latlng_to_lonlat(s.get("end_latlng"))
        if not sl or not el:
            continue
        waypoints.append(sl)
        waypoints.append(el)
        picks_summary.append({
            "id": s.get("id"),
            "name": s.get("name"),
            "distance_m": s.get("distance"),
            "athlete_count": s.get("athlete_count", 0),
            "effort_count": s.get("effort_count", 0),
            "start_latlng": s.get("start_latlng"),
            "end_latlng": s.get("end_latlng"),
        })
    if not picks_summary:
        return {"segments": [], "waypoints": [], "note": "no segments with routable endpoints"}
    waypoints.append(start)
    return {"segments": picks_summary, "waypoints": waypoints}


async def find_own_history_overlap(
    token: str,
    route_coords: List[List[float]],
    per_page: int = 30,
    overlap_threshold: float = 0.25,
    max_dist_m: float = 60.0,
) -> Dict:
    """Look at the connected athlete's own recent activities; return the ones
    whose map summary_polyline overlaps the current route. Real "you were
    here before" signal.
    """
    status, data = await strava_get(
        token, "/athlete/activities", {"per_page": per_page, "page": 1}
    )
    if status >= 400:
        return {"error": data, "matches": []}
    matches = []
    for a in data or []:
        stype = (a.get("sport_type") or a.get("type") or "").lower()
        if "run" not in stype:
            continue
        poly = ((a.get("map") or {}).get("summary_polyline") or "").strip()
        if not poly:
            continue
        try:
            decoded = polyline.decode(poly)
        except Exception:
            continue
        overlap = score_segment_overlap(route_coords, decoded, max_dist_m=max_dist_m)
        if overlap >= overlap_threshold:
            matches.append({
                "id": a.get("id"),
                "name": a.get("name"),
                "start_date_local": a.get("start_date_local"),
                "distance_m": a.get("distance"),
                "moving_time_s": a.get("moving_time"),
                "avg_speed": a.get("average_speed"),
                "overlap": round(overlap, 3),
            })
    matches.sort(key=lambda x: x["overlap"], reverse=True)
    return {"matches": matches[:6], "checked": len(data or [])}


async def rank_segments_along_route(
    token: str,
    route_coords: List[List[float]],
    activity_type: str = "running",
    max_dist_m: float = 40.0,
    min_overlap: float = 0.35,
) -> Dict:
    """Fetch segments in the route's bbox and score how well each overlaps."""
    south, west, north, east = _bbox(route_coords)
    status, data = await strava_get(
        token,
        "/segments/explore",
        {"bounds": f"{south},{west},{north},{east}", "activity_type": activity_type},
    )
    if status == 429:
        return {"error": "rate_limited", "segments": [], "score": 0}
    if status >= 400:
        return {"error": data, "segments": [], "score": 0}
    raw_segments = data.get("segments", [])

    ranked = []
    for s in raw_segments:
        poly = (s.get("points") or s.get("map", {}).get("polyline")) if isinstance(s, dict) else None
        if not poly:
            continue
        try:
            decoded = polyline.decode(poly)  # list of (lat, lon)
        except Exception:
            continue
        overlap = score_segment_overlap(route_coords, decoded, max_dist_m=max_dist_m)
        if overlap < min_overlap:
            continue
        ranked.append({
            "id": s.get("id"),
            "name": s.get("name"),
            "distance_m": s.get("distance"),
            "avg_grade": s.get("avg_grade") or s.get("average_grade"),
            "elev_difference": s.get("elev_difference"),
            "climb_category": s.get("climb_category"),
            "athlete_count": s.get("athlete_count") or 0,
            "effort_count": s.get("effort_count") or 0,
            "start_latlng": s.get("start_latlng"),
            "end_latlng": s.get("end_latlng"),
            "polyline": poly,
            "overlap": round(overlap, 3),
        })

    # Sort by (overlap × athlete_count) so we surface both popular AND on-route
    ranked.sort(key=lambda x: (x["overlap"] * (x["athlete_count"] or 1)), reverse=True)

    # Overall "tested" score for the route: how many athletes have run *some*
    # part of this loop across all overlapping segments, normalized.
    total_athletes = sum(s["athlete_count"] for s in ranked)
    covered_overlap = sum(s["overlap"] for s in ranked)
    score = _confidence_score(total_athletes, covered_overlap, len(ranked))

    return {
        "segments": ranked[:20],
        "total_segments_considered": len(raw_segments),
        "overlapping_count": len(ranked),
        "total_athletes": total_athletes,
        "score": score,
        "score_bucket": _score_bucket(score),
        "bbox": {"south": south, "west": west, "north": north, "east": east},
    }


def _confidence_score(total_athletes: int, covered_overlap: float, seg_count: int) -> int:
    """0..100 heuristic: log-scaled athlete count × segment coverage.

    - 0 overlapping segments → 0
    - a handful of low-usage segments → 30ish
    - many high-usage segments overlapping heavily → 90+
    """
    if seg_count == 0 or total_athletes <= 0:
        return 0
    athletes_score = min(60, 60 * math.log10(1 + total_athletes) / math.log10(1 + 5000))
    coverage_score = min(40, 40 * covered_overlap / max(3.0, seg_count * 0.7))
    return int(round(athletes_score + coverage_score))


def _score_bucket(s: int) -> str:
    if s >= 75:
        return "battle-tested"
    if s >= 55:
        return "well-run"
    if s >= 35:
        return "some traffic"
    if s > 0:
        return "quiet route"
    return "unrun"


# ---------------- GPX export ----------------

def build_gpx(name: str, coords: List[List[float]], elevations: Optional[List[float]] = None) -> str:
    """Return a GPX 1.1 XML string for the given [lon, lat] coordinates."""
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Trailscribe" xmlns="http://www.topografix.com/GPX/1/1">',
        f"  <metadata><name>{_x(name)}</name><time>{stamp}</time></metadata>",
        "  <trk>",
        f"    <name>{_x(name)}</name>",
        "    <trkseg>",
    ]
    for i, c in enumerate(coords):
        lon, lat = c[0], c[1]
        ele = ""
        if elevations and i < len(elevations):
            ele = f"<ele>{elevations[i]:.1f}</ele>"
        parts.append(f'      <trkpt lat="{lat}" lon="{lon}">{ele}</trkpt>')
    parts += ["    </trkseg>", "  </trk>", "</gpx>"]
    return "\n".join(parts)


def _x(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )
