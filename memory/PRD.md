# Trailscribe — Running Route Agent

## Problem Statement
Create a running route agent that takes start point, distance, pace groups, and constraints (loop not out-and-back, water stop midway, avoid highways, well-lit for a 5:30am start) and produces a route. The virtue is that it fails instructively: LLMs are bad at geometry and will produce routes that don't close, cross a river without a bridge, or measure 6km as 10. The system moves routing to a real maps API (OpenRouteService) while keeping the LLM for constraint interpretation and narration — the exact architecture trade-off the exercise is probing. Optional: connect Strava for discovery; make natural-language "ups and downs" narration of every path for new cities.

## Architecture
- **Backend (FastAPI + Motor + MongoDB)** — `/app/backend/server.py`
  - `POST /api/routes/generate` — full pipeline
    1. LLM (Claude Sonnet 5 or Gemini 3.1 Pro via emergentintegrations) *guesses* waypoints
    2. OpenRouteService `foot-walking/round_trip` generates the real closed-loop geometry with elevation
    3. Compare LLM guess vs real → write to `failure_log` (distance error %, hallucinated waypoint drift, non-closing loops)
    4. LLM narrates the real elevation profile with ups/downs, safety, water-stop rationale
  - `GET /api/discovery?city=bengaluru|delhi` — mock Strava-style curated routes
  - `POST /api/routes/save`, `GET /api/routes/saved` — Mongo persistence
- **Frontend (React 19 + Mapbox GL + Recharts + shadcn UI + framer-motion)**
  - Split-pane: 440px sidebar (Builder + Discovery tabs, Failure Log panel) + Mapbox dark-v11 map
  - Volt-yellow route line, cyan water-stop marker, pulsing start marker
  - Floating glass Narration Panel (top-right) with segment breakdown
  - Elevation Profile chart docked at bottom

## Personas
- **New-city runner** who wants an early-morning loop that's safe and honest about hills
- **Route curator** who wants to see the LLM's failures made visible before trusting the geometry

## Static Requirements
- Real map API for geometry (OpenRouteService)
- LLM for narration + constraint interpretation (Claude / Gemini)
- Instructive failure log surfaced in the UI
- Default cities: Bengaluru & Delhi
- 5:30am safety framing baked into narration prompt

## Implemented (2026-02-18)
- LLM guess → ORS real routing → failure log → LLM narration pipeline
- Mapbox map with loop rendering, elevation profile, narration glass panel
- Discovery grid (4 Bengaluru + 4 Delhi curated routes)
- Save / copy GPS actions
- Custom start via map click

## Implemented (2026-02-18 later)
- **Delhi city-switch fix**: setCity now clears customStart + previous route
- **Turn-by-Turn panel**: collapsible list of ORS steps with distance-to-next
- **Weather-aware narration**: Open-Meteo (temperature, AQI, sunrise, UV, wind) feeds the LLM prompt; UI shows chip strip; failure_log entry per fetch
- **Hardened LLM JSON parsing**: raw_decode + retry + explicit parse-ok signal; log warn on placeholder fallback
- **Weather cache** (15 min per lat/lon/hour) to survive Open-Meteo quota

## Implemented (2026-02-18 evening)
- **Real Strava OAuth** (Client 276007): /api/strava/authorize + /callback + /status + /logout; signed HttpOnly cookie session; scopes read,activity:read,activity:read_all,profile:read_all
- **Strava segment ranking**: /api/routes/rank_by_strava uses /segments/explore bbox → decodes polylines → overlap-scores segments within 40m of the generated route → 0-100 "safe & tested" score with buckets (battle-tested/well-run/some traffic/quiet route/unrun)
- **/api/strava/city_segments**: real Strava explore for a city bbox ranked by athlete_count
- **GPX 1.1 export** /api/routes/gpx (rejects empty coord arrays)
- **Push to Strava Route Builder** — copies coords + opens routes/new in a new tab
- Sidebar StravaConnect (orange), StravaSafety panel with clickable segment links

## Backlog
- P1: Native Strava upload (needs `activity:write` scope)
- P1: 5th curated route per city so digest picks hit 5
- P2: Live email via Resend (needs user's key)
- P2: Segment overlay on map with hover popups
- P2: Custom time picker matching Nordic Calm

## Implemented (2026-02-19 later)
- **Route accuracy retry**: `generate_loop_route` now tries up to 4 attempts, correcting the ORS `round_trip.length` by the inverse overshoot ratio each time. Every attempt lands in `failure_log` as `[ors_retry]`, plus a final `Converged to X%` or `Best-of-N` line. Response gains `retry_stats {attempts, final_err_pct, converged, tolerance_pct}`. Real convergence: 5-8km asks now hit ±15% within 1-3 attempts.
- **Strava-popularity routing**: new POST `/api/routes/generate_from_strava` picks top-athlete_count segments near the start (bbox scaled by distance), orders them nearest-neighbour, and calls ORS foot-walking with those as waypoints. Response adds `via_strava_segments` + `source:"strava_popular"`. Falls back to `/routes/generate` if no popular segments are nearby. UI: 'Route through popular Strava paths' toggle (Strava-connected only) in Builder.
- **8 narrator models**: claude sonnet 5, claude haiku 4.5, gemini 3.1 pro, gemini 3.5 flash, gemini 2.5 flash (labelled Lite), gpt 5.6 terra, gpt 5.6 luna, gpt 5 mini — each labeled rich / fast / fastest in the Select. gemini-lite mapping updated to `gemini-2.5-flash` (the -lite model wasn't available on the key).
