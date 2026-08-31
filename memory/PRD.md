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

## Backlog
- P1: Real Strava OAuth + MCP route discovery
- P1: Turn-by-turn instructions overlay
- P2: Multi-loop / out-and-back variants
- P2: GPX export
- P2: Save to public shareable URL
