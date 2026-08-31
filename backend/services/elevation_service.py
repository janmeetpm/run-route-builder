"""Open-Elevation fallback (ORS already returns elevation, but this is a
sanity check + backup)."""
import httpx
from typing import List


async def open_elevation(coords: List[List[float]]) -> List[float]:
    """coords is list of [lon, lat]. Returns list of elevations in meters."""
    if not coords:
        return []
    # Down-sample if too many points (API cap)
    sample = coords if len(coords) <= 90 else coords[:: max(1, len(coords) // 90)]
    body = {"locations": [{"latitude": c[1], "longitude": c[0]} for c in sample]}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post("https://api.open-elevation.com/api/v1/lookup", json=body)
        if r.status_code != 200:
            return []
        results = r.json().get("results", [])
        return [pt.get("elevation", 0.0) for pt in results]
