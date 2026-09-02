"""LLM services: (1) instructive-failure route guess, (2) narration.

We deliberately ask the LLM to *guess* route waypoints so we can log where
its geometry fails vs the real map API. Then we ask it to narrate the
ups/downs of the real route.
"""
import os
import json
import re
import uuid
from typing import Dict, List, Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage


PROVIDERS = {
    "claude": ("anthropic", "claude-sonnet-5"),
    "claude-haiku": ("anthropic", "claude-haiku-4-5-20251001"),
    "gemini": ("gemini", "gemini-3.1-pro-preview"),
    "gemini-flash": ("gemini", "gemini-3.5-flash"),
    "gemini-lite": ("gemini", "gemini-2.5-flash"),
    "gpt-terra": ("openai", "gpt-5.6-terra"),
    "gpt-luna": ("openai", "gpt-5.6-luna"),
    "gpt-mini": ("openai", "gpt-5-mini"),
}


def _extract_json(text: str) -> Dict:
    """Robustly extract the first JSON object from an LLM response.

    Strategy: prefer a ```json fenced block, else use json.JSONDecoder.raw_decode
    from the first '{' so trailing prose / additional JSON blocks are ignored.
    strict=False allows literal newlines inside string values.
    """
    if not text:
        raise ValueError("empty LLM response")

    # 1) Prefer fenced block
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    candidates: List[str] = []
    if m:
        candidates.append(m.group(1))
    # 2) raw_decode from first '{'
    idx = text.find("{")
    if idx != -1:
        candidates.append(text[idx:])

    decoder = json.JSONDecoder(strict=False)
    last_err: Optional[Exception] = None
    for c in candidates:
        try:
            obj, _ = decoder.raw_decode(c)
            return obj
        except Exception as e:  # pragma: no cover
            last_err = e
    raise ValueError(f"No parseable JSON in LLM response: {last_err} :: {text[:200]}")


async def llm_guess_route(
    provider: str,
    start_name: str,
    start_lon: float,
    start_lat: float,
    distance_km: float,
    constraints: Dict,
) -> Dict:
    """Ask the LLM to hallucinate a plausible loop route.

    Returns dict with `waypoints` [[lon,lat], ...], `estimated_distance_km`,
    `estimated_ascent_m`, and `reasoning`. This is the "failing side" that
    we compare against real routing.
    """
    key = os.environ["EMERGENT_LLM_KEY"]
    prov, model = PROVIDERS.get(provider, PROVIDERS["claude"])
    session_id = f"guess-{uuid.uuid4().hex[:8]}"
    last_err: Optional[Exception] = None

    system = (
        "You are a running route planner. You will estimate a loop route "
        "purely from geographic reasoning. Return ONLY compact JSON, no prose."
    )
    prompt = f"""Plan a loop running route in {start_name}.
Start: lon={start_lon}, lat={start_lat}
Target distance: {distance_km} km
Constraints: {json.dumps(constraints)}

Return JSON exactly of shape:
{{
  "waypoints": [[lon,lat], [lon,lat], [lon,lat], [lon,lat], [lon,lat]],
  "estimated_distance_km": number,
  "estimated_ascent_m": number,
  "reasoning": "one short sentence"
}}
The first and last waypoint MUST equal the start. Include 3-6 intermediate waypoints."""

    chat = LlmChat(api_key=key, session_id=session_id, system_message=system).with_model(prov, model)
    # Try once, retry once on parse failure — LLMs occasionally emit trailing prose.
    for attempt in range(2):
        resp = await chat.send_message(UserMessage(text=prompt))
        try:
            out = _extract_json(resp)
            out["_parse_ok"] = True
            return out
        except Exception as e:
            last_err = e
            continue
    return {
        "waypoints": [[start_lon, start_lat]],
        "estimated_distance_km": distance_km,
        "estimated_ascent_m": 0,
        "reasoning": "LLM output could not be parsed",
        "_parse_ok": False,
        "_parse_error": str(last_err)[:180],
    }


async def llm_narrate_route(
    provider: str,
    start_name: str,
    distance_km: float,
    elev_stats: Dict,
    elevations: List[float],
    constraints: Dict,
    steps_preview: List[Dict],
    weather: Optional[Dict] = None,
) -> Dict:
    """Ask the LLM to narrate the actual route in plain, evocative language."""
    key = os.environ["EMERGENT_LLM_KEY"]
    prov, model = PROVIDERS.get(provider, PROVIDERS["claude"])
    session_id = f"narrate-{uuid.uuid4().hex[:8]}"

    # Downsample elevation to ~12 points for the LLM
    n = len(elevations)
    stride = max(1, n // 12)
    elev_sample = [round(e, 1) for e in elevations[::stride]]

    system = (
        "You are a warm, grounded running coach who narrates routes vividly. "
        "You describe ups, downs, texture underfoot, atmosphere, safety, and pacing "
        "in a natural, human way. When weather, air-quality, or sunrise data is provided, "
        "weave a concrete, non-generic 1-sentence shade / AQI / darkness note into the "
        "safety_note and reflect the conditions in the narration itself. Return strict JSON only."
    )
    prompt = f"""Route in {start_name}, distance {round(distance_km, 2)} km.
Elevation stats: {json.dumps(elev_stats)}
Elevation profile sample (meters): {elev_sample}
Constraints requested: {json.dumps(constraints)}
Turn preview: {json.dumps([s.get('instruction') for s in steps_preview[:6]])}
Weather snapshot: {json.dumps(weather) if weather else 'unavailable'}

Return JSON:
{{
  "headline": "3-6 word evocative name for the route",
  "narration": "2-3 paragraph description of ups and downs, feel, light, safety. Address the runner as 'you'. If weather is provided, mention temperature, air quality, or pre-dawn darkness where it matters.",
  "segments": [
    {{"label": "Warm-up", "km_start": 0, "km_end": ..., "vibe": "..."}},
    {{"label": "The Climb", "km_start": ..., "km_end": ..., "vibe": "..."}}
  ],
  "safety_note": "1 concrete sentence tied to today's conditions (AQI bucket, sunrise timing, wind, or UV). Not generic.",
  "water_stop_pitch": "1 short sentence explaining why the midway water stop makes sense today (heat/humidity/UV)"
}}"""

    chat = LlmChat(api_key=key, session_id=session_id, system_message=system).with_model(prov, model)
    last_err: Optional[Exception] = None
    for attempt in range(2):
        resp = await chat.send_message(UserMessage(text=prompt))
        try:
            out = _extract_json(resp)
            out["_parse_ok"] = True
            return out
        except Exception as e:
            last_err = e
            continue
    return {
        "headline": f"{round(distance_km, 1)}km Loop",
        "narration": "Route narration unavailable — see turn-by-turn instructions.",
        "segments": [],
        "safety_note": "Wear reflective gear for the pre-dawn start.",
        "water_stop_pitch": "Midway refill keeps your pace honest.",
        "_parse_ok": False,
        "_parse_error": str(last_err)[:180],
    }
