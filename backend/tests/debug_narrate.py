"""Debug harness: capture the raw LLM narration response to RCA the JSON parse fallback."""
import asyncio
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv(Path("/app/backend/.env"))

from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: E402
from services.llm_service import PROVIDERS, _extract_json  # noqa: E402


async def main(provider="claude"):
    key = os.environ["EMERGENT_LLM_KEY"]
    prov, model = PROVIDERS[provider]
    system = (
        "You are a warm, grounded running coach who narrates routes vividly. "
        "You describe ups, downs, texture underfoot, atmosphere, safety, and pacing "
        "in a natural, human way. When weather, air-quality, or sunrise data is provided, "
        "weave a concrete, non-generic 1-sentence shade / AQI / darkness note into the "
        "safety_note and reflect the conditions in the narration itself. Return strict JSON only."
    )
    weather = {
        "temperature_c": 23.4, "aqi": 62, "aqi_bucket": "poor",
        "sunrise": "2026-07-01T05:58", "before_sunrise": True, "wind_kmh": 6.2,
        "precip_prob_pct": 20, "uv_index_max": 9.1,
    }
    prompt = f"""Route in Cubbon Park Gate 4, Bengaluru, distance 4.61 km.
Elevation stats: {{"ascent_m": 30, "descent_m": 30, "min_m": 900, "max_m": 930}}
Elevation profile sample (meters): [900, 905, 910, 915, 920, 925, 930, 925, 920, 915, 910, 905]
Constraints requested: {{"loop": true, "water_stop": true, "avoid_highways": true, "well_lit": true, "start_time": "05:30"}}
Turn preview: ["Head north", "Turn right", "Continue", "Turn left", "Turn right", "Arrive"]
Weather snapshot: {json.dumps(weather)}

Return JSON:
{{
  "headline": "3-6 word evocative name for the route",
  "narration": "2-3 paragraph description of ups and downs, feel, light, safety. Address the runner as 'you'. If weather is provided, mention temperature, air quality, or pre-dawn darkness where it matters.",
  "segments": [
    {{"label": "Warm-up", "km_start": 0, "km_end": 1, "vibe": "..."}}
  ],
  "safety_note": "1 concrete sentence tied to today's conditions.",
  "water_stop_pitch": "1 short sentence"
}}"""
    chat = LlmChat(api_key=key, session_id="dbg-1", system_message=system).with_model(prov, model)
    resp = await chat.send_message(UserMessage(text=prompt))
    print("=== RAW LEN:", len(resp))
    print(repr(resp[:400]))
    print("...TAIL...")
    print(repr(resp[-400:]))
    try:
        parsed = _extract_json(resp)
        print("PARSE OK. narration len:", len(parsed.get("narration", "")))
    except Exception as e:
        print("PARSE FAILED:", type(e).__name__, e)


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "claude"))
