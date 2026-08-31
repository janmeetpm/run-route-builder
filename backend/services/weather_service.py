"""Weather + air-quality + sunrise for the route start point.

Uses Open-Meteo (free, no API key). Returns a compact snapshot that the LLM
narration can consume and that the UI can render as a chip strip.
"""
import httpx
import time
from typing import Dict, Tuple


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Small in-process cache to avoid burning the daily Open-Meteo quota
# key = (round(lat,2), round(lon,2), hh_bucket); value = (expires_at_epoch, snapshot)
_CACHE: Dict[Tuple[float, float, str], Tuple[float, Dict]] = {}
_CACHE_TTL_S = 15 * 60  # 15 minutes


def _aqi_bucket(aqi: float) -> str:
    if aqi is None:
        return "unknown"
    if aqi <= 20:
        return "good"
    if aqi <= 40:
        return "fair"
    if aqi <= 60:
        return "moderate"
    if aqi <= 80:
        return "poor"
    if aqi <= 100:
        return "very poor"
    return "extremely poor"


async def fetch_weather_snapshot(lat: float, lon: float, start_time_hhmm: str = "05:30") -> Dict:
    """Fetch temperature, wind, precip probability, AQI, sunrise/sunset for today.

    Returns a dict safe to serialize and to hand to the LLM.
    Uses a 15-minute in-process cache keyed by (lat, lon, hour) to avoid
    exhausting the Open-Meteo daily quota.
    """
    cache_key = (round(lat, 2), round(lon, 2), start_time_hhmm)
    cached = _CACHE.get(cache_key)
    if cached and cached[0] > time.time():
        return cached[1]
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,apparent_temperature,relative_humidity_2m",
        "daily": "sunrise,sunset,uv_index_max",
        "timezone": "auto",
        "forecast_days": 1,
    }
    aqi_params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "european_aqi,pm2_5,pm10",
        "timezone": "auto",
        "forecast_days": 1,
    }

    async with httpx.AsyncClient(timeout=12) as client:
        wr, ar = await _gather(client, params, aqi_params)

    result: Dict = {
        "provider": "open-meteo",
        "start_time": start_time_hhmm,
        "sunrise": None,
        "sunset": None,
        "temperature_c": None,
        "feels_like_c": None,
        "humidity_pct": None,
        "wind_kmh": None,
        "precip_prob_pct": None,
        "uv_index_max": None,
        "aqi": None,
        "aqi_bucket": "unknown",
        "pm25": None,
        "pm10": None,
        "before_sunrise": None,
        "forecast_status": None,  # None|"ok"|"rate_limited"|"error"
        "aqi_status": None,
    }

    # Track upstream statuses so the server-side failure_log can be honest
    result["forecast_status"] = "ok" if wr else "unavailable"
    result["aqi_status"] = "ok" if ar else "unavailable"

    if wr:
        daily = wr.get("daily") or {}
        sunrises = daily.get("sunrise") or []
        sunsets = daily.get("sunset") or []
        result["sunrise"] = sunrises[0] if sunrises else None
        result["sunset"] = sunsets[0] if sunsets else None
        uvm = daily.get("uv_index_max") or []
        result["uv_index_max"] = uvm[0] if uvm else None

        hourly = wr.get("hourly") or {}
        times = hourly.get("time") or []
        idx = _hour_index(times, start_time_hhmm)
        if idx is not None:
            result["temperature_c"] = _at(hourly.get("temperature_2m"), idx)
            result["feels_like_c"] = _at(hourly.get("apparent_temperature"), idx)
            result["humidity_pct"] = _at(hourly.get("relative_humidity_2m"), idx)
            result["wind_kmh"] = _at(hourly.get("wind_speed_10m"), idx)
            result["precip_prob_pct"] = _at(hourly.get("precipitation_probability"), idx)

        # Before sunrise?
        try:
            if result["sunrise"]:
                sr_hour = int(result["sunrise"].split("T")[1].split(":")[0])
                sr_min = int(result["sunrise"].split("T")[1].split(":")[1])
                sh, sm = [int(x) for x in start_time_hhmm.split(":")]
                result["before_sunrise"] = (sh, sm) < (sr_hour, sr_min)
        except Exception:
            pass

    if ar:
        hourly = ar.get("hourly") or {}
        times = hourly.get("time") or []
        idx = _hour_index(times, start_time_hhmm)
        if idx is not None:
            result["aqi"] = _at(hourly.get("european_aqi"), idx)
            result["pm25"] = _at(hourly.get("pm2_5"), idx)
            result["pm10"] = _at(hourly.get("pm10"), idx)
            result["aqi_bucket"] = _aqi_bucket(result["aqi"])

    _CACHE[cache_key] = (time.time() + _CACHE_TTL_S, result)
    return result


async def _gather(client, wparams, aparams):
    import asyncio

    async def get(url, params):
        try:
            r = await client.get(url, params=params)
            if r.status_code == 200:
                return r.json()
        except Exception:
            return None
        return None

    wr, ar = await asyncio.gather(get(FORECAST_URL, wparams), get(AQI_URL, aparams))
    return wr, ar


def _hour_index(times, hhmm):
    if not times:
        return None
    hh = int(hhmm.split(":")[0])
    # Times look like "2026-02-18T00:00" — find first entry whose hour == hh
    for i, t in enumerate(times):
        try:
            th = int(t.split("T")[1].split(":")[0])
            if th == hh:
                return i
        except Exception:
            continue
    return 0


def _at(arr, i):
    if not arr or i is None or i >= len(arr):
        return None
    v = arr[i]
    return round(v, 1) if isinstance(v, (int, float)) else v
