"""Strava API v3 integration: OAuth, segments, activities, and route→segment
overlap scoring for the 'safe & tested' route ranking.

Single-user session model (Emergent preview): OAuth session state and the
resulting token are stored in Mongo under a signed cookie's session id.
Tokens auto-refresh 60s before expiry.
"""
import os
import time
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
