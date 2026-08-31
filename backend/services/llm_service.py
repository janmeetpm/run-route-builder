"""LLM services: (1) instructive-failure route guess, (2) narration.

We deliberately ask the LLM to *guess* route waypoints so we can log where
its geometry fails vs the real map API. Then we ask it to narrate the
ups/downs of the real route.
"""
import os
import json
import re
import uuid
from typing import Dict, List

from emergentintegrations.llm.chat import LlmChat, UserMessage


PROVIDERS = {
    "claude": ("anthropic", "claude-sonnet-5"),
    "gemini": ("gemini", "gemini-3.1-pro-preview"),
}


def _extract_json(text: str) -> Dict:
    """Extract first {...} JSON block from an LLM response."""
    # Strip markdown code fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    # Grab from first { to last }
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON in LLM response: {text[:200]}")
    return json.loads(cleaned[start : end + 1])


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
    resp = await chat.send_message(UserMessage(text=prompt))
    try:
        return _extract_json(resp)
    except Exception:
        # Fallback synthetic guess if parsing fails
        return {
            "waypoints": [[start_lon, start_lat]],
            "estimated_distance_km": distance_km,
            "estimated_ascent_m": 0,
            "reasoning": "LLM output could not be parsed",
        }


async def llm_narrate_route(
    provider: str,
    start_name: str,
    distance_km: float,
    elev_stats: Dict,
    elevations: List[float],
    constraints: Dict,
    steps_preview: List[Dict],
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
        "in a natural, human way. Return strict JSON only."
    )
    prompt = f"""Route in {start_name}, distance {round(distance_km, 2)} km.
Elevation stats: {json.dumps(elev_stats)}
Elevation profile sample (meters): {elev_sample}
Constraints requested: {json.dumps(constraints)}
Turn preview: {json.dumps([s.get('instruction') for s in steps_preview[:6]])}

Return JSON:
{{
  "headline": "3-6 word evocative name for the route",
  "narration": "2-3 paragraph description of ups and downs, feel, light, safety. Address the runner as 'you'.",
  "segments": [
    {{"label": "Warm-up", "km_start": 0, "km_end": ..., "vibe": "..."}},
    {{"label": "The Climb", "km_start": ..., "km_end": ..., "vibe": "..."}},
    ...
  ],
  "safety_note": "1 short sentence about the 5:30am start conditions",
  "water_stop_pitch": "1 short sentence explaining why the midway water stop makes sense"
}}"""

    chat = LlmChat(api_key=key, session_id=session_id, system_message=system).with_model(prov, model)
    resp = await chat.send_message(UserMessage(text=prompt))
    try:
        return _extract_json(resp)
    except Exception:
        return {
            "headline": f"{round(distance_km, 1)}km Loop",
            "narration": "Route narration unavailable — see turn-by-turn instructions.",
            "segments": [],
            "safety_note": "Wear reflective gear for the pre-dawn start.",
            "water_stop_pitch": "Midway refill keeps your pace honest.",
        }
