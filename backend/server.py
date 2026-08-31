from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Cookie
from fastapi.responses import RedirectResponse, PlainTextResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import time
import hashlib
import secrets as pysecrets
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from services.route_service import generate_loop_route, compute_elevation_stats, _haversine_m
from services.llm_service import llm_guess_route, llm_narrate_route
from services.weather_service import fetch_weather_snapshot
from services.mock_strava import list_discovery
from services import strava_service as strava

# Mongo
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Trailscribe Route Agent")
api_router = APIRouter(prefix="/api")


# ---------- Models ----------

class Constraints(BaseModel):
    loop: bool = True
    water_stop: bool = True
    avoid_highways: bool = True
    well_lit: bool = True
    start_time: str = "05:30"


class GenerateRouteRequest(BaseModel):
    start_name: str
    start_lon: float
    start_lat: float
    distance_km: float
    pace_group: str = "easy"  # easy | tempo | long
    provider: str = "claude"  # claude | gemini
    constraints: Constraints = Field(default_factory=Constraints)
    seed: Optional[int] = None


class SavedRoute(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    city: str
    distance_km: float
    ascent_m: float
    provider: str
    coordinates: List[List[float]]
    elevations: List[float]
    cumulative_distance_m: List[float]
    narration: Dict[str, Any]
    failure_log: List[Dict[str, Any]]
    midpoint: List[float]
    weather: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------- Routes ----------

@api_router.get("/")
async def root():
    return {"service": "trailscribe", "status": "ok"}


@api_router.get("/discovery")
async def discovery(city: str):
    """Mock Strava-style curated routes for Bengaluru / Delhi."""
    routes = list_discovery(city)
    if not routes:
        raise HTTPException(404, f"No routes for city '{city}'")
    return {"city": city, "routes": routes}


CITY_BBOX = {
    # south, west, north, east
    "bengaluru": (12.87, 77.49, 13.10, 77.75),
    "delhi": (28.52, 77.10, 28.75, 77.34),
}


@api_router.get("/strava/city_segments")
async def strava_city_segments(request: Request, city: str, activity_type: str = "running"):
    """Real Strava segments for a city, ranked by athlete_count."""
    if city.lower() not in CITY_BBOX:
        raise HTTPException(404, f"City '{city}' not configured")
    sid = _get_sid(request)
    if not sid:
        raise HTTPException(401, "Connect Strava first")
    token = await strava.valid_access_token(db, sid)
    if not token:
        raise HTTPException(401, "Strava token unavailable, please reconnect")
    south, west, north, east = CITY_BBOX[city.lower()]
    status, data = await strava.strava_get(
        token, "/segments/explore",
        {"bounds": f"{south},{west},{north},{east}", "activity_type": activity_type},
    )
    if status >= 400:
        raise HTTPException(status, str(data)[:300])
    segs = data.get("segments", [])
    segs.sort(key=lambda s: (s.get("athlete_count", 0), s.get("effort_count", 0)), reverse=True)
    return {"city": city, "segments": segs[:20]}


@api_router.post("/routes/generate")
async def generate(req: GenerateRouteRequest):
    """Full pipeline: LLM guess (fails) → real ORS route → LLM narration."""
    failure_log: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    # --- Step 1: LLM's naive guess (the "instructive failure") ---
    try:
        guess = await llm_guess_route(
            provider=req.provider,
            start_name=req.start_name,
            start_lon=req.start_lon,
            start_lat=req.start_lat,
            distance_km=req.distance_km,
            constraints=req.constraints.model_dump(),
        )
        if guess.get("_parse_ok") is False:
            failure_log.append({
                "t": now, "level": "warn", "stage": "llm_guess",
                "message": f"LLM guess unparseable, using synthetic fallback: {guess.get('_parse_error', '')}",
            })
    except Exception as e:
        guess = {"waypoints": [], "estimated_distance_km": req.distance_km, "reasoning": f"LLM error: {e}", "estimated_ascent_m": 0}
        failure_log.append({
            "t": now, "level": "warn", "stage": "llm_guess",
            "message": f"LLM refused: {str(e)[:120]}",
        })

    # --- Step 2: Real routing via OpenRouteService ---
    try:
        route = await generate_loop_route(
            lon=req.start_lon,
            lat=req.start_lat,
            distance_km=req.distance_km,
            avoid_highways=req.constraints.avoid_highways,
            seed=req.seed,
        )
    except Exception as e:
        raise HTTPException(502, f"Routing failed: {e}")

    elev_stats = compute_elevation_stats(route["elevations"])
    actual_km = round(route["distance_m"] / 1000, 2)

    # --- Step 3: Compare & log failures ---
    est_km = float(guess.get("estimated_distance_km", 0) or 0)
    dist_err_pct = abs(est_km - actual_km) / max(actual_km, 0.01) * 100 if actual_km else 0
    failure_log.append({
        "t": now,
        "level": "info",
        "stage": "llm_geometry_check",
        "message": f"LLM estimated {est_km:.2f} km  |  Real geometry {actual_km:.2f} km  |  error {dist_err_pct:.1f}%",
    })

    # Surface ORS overshoot vs requested distance
    ors_err_pct = abs(actual_km - req.distance_km) / max(req.distance_km, 0.01) * 100
    if ors_err_pct > 20:
        failure_log.append({
            "t": now, "level": "warn", "stage": "ors_routing",
            "message": f"ORS round-trip overshot request by {ors_err_pct:.0f}% ({req.distance_km}km asked, {actual_km}km delivered). Try a different seed for a tighter fit.",
        })

    # Check LLM waypoints for silliness
    wpts = guess.get("waypoints") or []
    if wpts:
        # Detect if waypoints wander >5km from start (geometry hallucination)
        max_drift = 0.0
        for w in wpts:
            try:
                d = _haversine_m([req.start_lon, req.start_lat], w) / 1000.0
                max_drift = max(max_drift, d)
            except Exception:
                pass
        expected_drift_km = req.distance_km / 3.0
        if max_drift > expected_drift_km * 2.5:
            failure_log.append({
                "t": now, "level": "error", "stage": "llm_geometry_check",
                "message": f"LLM waypoint drifted {max_drift:.1f}km from start (expected ~{expected_drift_km:.1f}km). Hallucinated geography.",
            })
        # Check if LLM's loop closes
        if len(wpts) >= 2:
            closure_m = _haversine_m(wpts[0], wpts[-1])
            if closure_m > 200:
                failure_log.append({
                    "t": now, "level": "error", "stage": "llm_geometry_check",
                    "message": f"LLM loop does not close: {closure_m:.0f}m gap between first/last waypoint.",
                })

    if dist_err_pct > 25:
        failure_log.append({
            "t": now, "level": "error", "stage": "llm_geometry_check",
            "message": f"LLM distance estimate off by {dist_err_pct:.0f}%. Handing routing to OpenRouteService.",
        })

    failure_log.append({
        "t": now, "level": "success", "stage": "ors_routing",
        "message": f"Real loop generated. {actual_km} km, ascent {elev_stats['ascent_m']}m, closed={route['closed']}.",
    })

    if not route["closed"]:
        failure_log.append({
            "t": now, "level": "warn", "stage": "ors_routing",
            "message": "Warning: real route did not close within 30m. Minor stitch applied.",
        })

    # --- Step 3.5: Weather + AQI + sunrise for the narration ---
    try:
        weather = await fetch_weather_snapshot(
            lat=req.start_lat, lon=req.start_lon, start_time_hhmm=req.constraints.start_time
        )
        has_core = weather and weather.get("temperature_c") is not None and weather.get("sunrise") is not None
        has_any = weather and any(
            weather.get(k) is not None for k in ("temperature_c", "sunrise", "aqi")
        )
        if has_core:
            level = "success"
            msg = (
                f"Weather fetched: {weather.get('temperature_c')}°C, "
                f"AQI {weather.get('aqi')} ({weather.get('aqi_bucket')}), "
                f"sunrise {weather.get('sunrise')}."
            )
        elif has_any:
            level = "warn"
            msg = (
                f"Partial weather: forecast={weather.get('forecast_status')}, "
                f"aqi={weather.get('aqi_status')}. "
                f"Temperature={weather.get('temperature_c')}, sunrise={weather.get('sunrise')}, "
                f"AQI={weather.get('aqi')}."
            )
        else:
            level = "warn"
            msg = "Weather fetch returned no usable data (Open-Meteo transient failure or rate limit)."
        failure_log.append({"t": now, "level": level, "stage": "weather", "message": msg})
    except Exception as e:
        weather = None
        failure_log.append({
            "t": now, "level": "warn", "stage": "weather",
            "message": f"Weather fetch failed: {str(e)[:100]}",
        })

    # --- Step 4: LLM narration on real geometry ---
    try:
        narration = await llm_narrate_route(
            provider=req.provider,
            start_name=req.start_name,
            distance_km=actual_km,
            elev_stats=elev_stats,
            elevations=route["elevations"],
            constraints=req.constraints.model_dump(),
            steps_preview=route["steps"],
            weather=weather,
        )
        if narration.get("_parse_ok") is False:
            failure_log.append({
                "t": now, "level": "warn", "stage": "llm_narration",
                "message": f"Narration JSON unparseable; served placeholder. Parse error: {narration.get('_parse_error', '')}",
            })
        else:
            failure_log.append({
                "t": now, "level": "success", "stage": "llm_narration",
                "message": f"Narration generated via {req.provider} on real elevation profile.",
            })
        # Strip internal signaling keys before returning to the client
        narration.pop("_parse_ok", None)
        narration.pop("_parse_error", None)
    except Exception as e:
        narration = {
            "headline": f"{actual_km}km Loop",
            "narration": "Narration unavailable.",
            "segments": [], "safety_note": "", "water_stop_pitch": "",
        }
        failure_log.append({
            "t": now, "level": "warn", "stage": "llm_narration",
            "message": f"Narration failed: {str(e)[:120]}",
        })

    result = {
        "id": str(uuid.uuid4()),
        "start_name": req.start_name,
        "start": [req.start_lon, req.start_lat],
        "distance_km": actual_km,
        "duration_s": route["duration_s"],
        "elev_stats": elev_stats,
        "coordinates": route["coordinates"],
        "elevations": route["elevations"],
        "cumulative_distance_m": route["cumulative_distance_m"],
        "steps": route["steps"],
        "midpoint": route["midpoint"],
        "closed": route["closed"],
        "narration": narration,
        "llm_guess": {
            "estimated_distance_km": est_km,
            "estimated_ascent_m": guess.get("estimated_ascent_m", 0),
            "reasoning": guess.get("reasoning", ""),
            "waypoint_count": len(wpts),
            "distance_error_pct": round(dist_err_pct, 1),
        },
        "failure_log": failure_log,
        "provider": req.provider,
        "constraints": req.constraints.model_dump(),
        "weather": weather,
    }
    return result


class SaveRouteRequest(BaseModel):
    name: str
    city: str
    distance_km: float
    ascent_m: float
    provider: str
    coordinates: List[List[float]]
    elevations: List[float]
    cumulative_distance_m: List[float]
    narration: Dict[str, Any]
    failure_log: List[Dict[str, Any]]
    midpoint: List[float]
    weather: Optional[Dict[str, Any]] = None


@api_router.post("/routes/save")
async def save_route(req: SaveRouteRequest):
    doc = SavedRoute(**req.model_dump()).model_dump()
    await db.saved_routes.insert_one(doc)
    return {"id": doc["id"], "saved": True}


@api_router.get("/routes/saved")
async def get_saved():
    docs = await db.saved_routes.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"routes": docs}


# ---------- Strava OAuth + segments ----------

STRAVA_COOKIE = "trailscribe_sid"


def _get_sid(request: Request) -> Optional[str]:
    raw = request.cookies.get(STRAVA_COOKIE)
    return strava.unsign_sid(raw) if raw else None


def _set_sid_cookie(response: Response, sid: str):
    response.set_cookie(
        STRAVA_COOKIE, strava.sign_sid(sid),
        httponly=True, secure=True, samesite="lax",
        max_age=60 * 60 * 24 * 30, path="/",
    )


@api_router.get("/strava/authorize")
async def strava_authorize(request: Request):
    sid = _get_sid(request) or strava.new_session_id()
    state = pysecrets.token_urlsafe(24)
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    await db.strava_sessions.update_one(
        {"_id": sid},
        {"$set": {"state_hash": state_hash, "updated_at": time.time()}},
        upsert=True,
    )
    url = strava.build_authorize_url(state)
    resp = RedirectResponse(url, status_code=307)
    _set_sid_cookie(resp, sid)
    return resp


@api_router.get("/strava/callback")
async def strava_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    scope: Optional[str] = None,
):
    frontend = os.environ.get("STRAVA_FRONTEND_URL", "/")
    if error:
        return RedirectResponse(f"{frontend}/?strava=error&reason={error}", status_code=303)
    if not code or not state:
        raise HTTPException(400, "Missing code/state from Strava")
    sid = _get_sid(request)
    if not sid:
        raise HTTPException(400, "Missing session cookie")
    doc = await db.strava_sessions.find_one({"_id": sid})
    expected = hashlib.sha256(state.encode()).hexdigest()
    if not doc or not pysecrets.compare_digest(doc.get("state_hash", ""), expected):
        raise HTTPException(400, "Invalid or expired OAuth state")

    try:
        tok = await strava.exchange_code(code)
    except Exception as e:
        return RedirectResponse(f"{frontend}/?strava=error&reason=token_exchange", status_code=303)

    athlete = tok.get("athlete") or {}
    await db.strava_sessions.update_one(
        {"_id": sid},
        {"$set": {
            "access_token": tok["access_token"],
            "refresh_token": tok["refresh_token"],
            "expires_at": tok["expires_at"],
            "scope": (scope or "").split(","),
            "athlete_id": athlete.get("id"),
            "athlete": {
                "id": athlete.get("id"),
                "firstname": athlete.get("firstname"),
                "lastname": athlete.get("lastname"),
                "profile": athlete.get("profile"),
                "city": athlete.get("city"),
                "country": athlete.get("country"),
            },
            "state_hash": None,
            "updated_at": time.time(),
        }},
    )
    return RedirectResponse(f"{frontend}/?strava=connected", status_code=303)


@api_router.get("/strava/status")
async def strava_status(request: Request):
    sid = _get_sid(request)
    if not sid:
        return {"connected": False}
    doc = await db.strava_sessions.find_one({"_id": sid})
    if not doc or not doc.get("access_token"):
        return {"connected": False}
    return {
        "connected": True,
        "athlete": doc.get("athlete") or {},
        "scope": doc.get("scope") or [],
        "expires_at": doc.get("expires_at"),
    }


@api_router.post("/strava/logout")
async def strava_logout(request: Request):
    sid = _get_sid(request)
    if sid:
        await db.strava_sessions.update_one(
            {"_id": sid},
            {"$unset": {"access_token": "", "refresh_token": "", "expires_at": "", "athlete": "", "athlete_id": ""}},
        )
    resp = Response(status_code=200)
    resp.delete_cookie(STRAVA_COOKIE, path="/")
    return resp


@api_router.get("/strava/activities")
async def strava_activities(request: Request, page: int = 1, per_page: int = 20):
    sid = _get_sid(request)
    if not sid:
        raise HTTPException(401, "Connect Strava first")
    token = await strava.valid_access_token(db, sid)
    if not token:
        raise HTTPException(401, "Strava token unavailable, please reconnect")
    status, data = await strava.strava_get(token, "/athlete/activities", {"page": page, "per_page": per_page})
    if status >= 400:
        raise HTTPException(status, str(data)[:300])
    # Only runs
    runs = [a for a in data if a.get("type") in ("Run", "TrailRun") or a.get("sport_type", "").endswith("Run")]
    return {"activities": runs}


class RankRequest(BaseModel):
    coordinates: List[List[float]]
    activity_type: str = "running"


@api_router.post("/routes/rank_by_strava")
async def rank_route_by_strava(req: RankRequest, request: Request):
    sid = _get_sid(request)
    if not sid:
        raise HTTPException(401, "Connect Strava first")
    token = await strava.valid_access_token(db, sid)
    if not token:
        raise HTTPException(401, "Strava token unavailable, please reconnect")
    result = await strava.rank_segments_along_route(
        token=token, route_coords=req.coordinates, activity_type=req.activity_type
    )
    return result


class GpxRequest(BaseModel):
    name: str = "Trailscribe route"
    coordinates: List[List[float]]
    elevations: Optional[List[float]] = None


@api_router.post("/routes/gpx")
async def route_gpx(req: GpxRequest):
    if not req.coordinates:
        raise HTTPException(422, "coordinates must be a non-empty list of [lon, lat] pairs")
    xml = strava.build_gpx(req.name, req.coordinates, req.elevations)
    safe = "".join(c for c in req.name if c.isalnum() or c in "-_")[:40] or "route"
    return PlainTextResponse(
        xml,
        media_type="application/gpx+xml",
        headers={"Content-Disposition": f'attachment; filename="{safe}.gpx"'},
    )


# ---------- App wiring ----------
app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
