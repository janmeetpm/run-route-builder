import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import { PANELS } from "@/constants/testIds";

const MAPBOX_TOKEN = process.env.REACT_APP_MAPBOX_TOKEN;
mapboxgl.accessToken = MAPBOX_TOKEN;

const CITY_CENTERS = {
  bengaluru: [77.5946, 12.9716],
  delhi: [77.209, 28.6139],
};

export default function RouteMap({ city, route, onMapClick }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const [ready, setReady] = useState(false);

  // Init map once
  useEffect(() => {
    if (mapRef.current) return;
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center: CITY_CENTERS[city] || CITY_CENTERS.bengaluru,
      zoom: 12.5,
      pitch: 25,
      attributionControl: false,
    });
    map.addControl(new mapboxgl.NavigationControl({ visualizePitch: true }), "bottom-right");
    map.on("load", () => {
      setReady(true);
    });
    map.on("click", (e) => {
      if (onMapClick) onMapClick([e.lngLat.lng, e.lngLat.lat]);
    });
    mapRef.current = map;
  }, []); // eslint-disable-line

  // Fly to city on change
  useEffect(() => {
    if (!mapRef.current || !ready) return;
    const c = CITY_CENTERS[city];
    if (c) mapRef.current.flyTo({ center: c, zoom: 12.5, duration: 1400, essential: true });
  }, [city, ready]);

  // Draw route
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    // Clear route layers/source (layer ids must match those created below)
    try {
      ["route-line-top", "route-glow"].forEach((id) => {
        if (map.getLayer(id)) map.removeLayer(id);
      });
      if (map.getSource("route-line")) map.removeSource("route-line");
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn("route cleanup:", e);
    }

    // Clear markers
    (map._runMarkers || []).forEach((m) => m.remove());
    map._runMarkers = [];

    if (!route || !route.coordinates?.length) return;

    const geojson = {
      type: "Feature",
      geometry: { type: "LineString", coordinates: route.coordinates },
    };

    map.addSource("route-line", { type: "geojson", data: geojson });
    map.addLayer({
      id: "route-glow",
      type: "line",
      source: "route-line",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": "#DFFF00",
        "line-width": 12,
        "line-opacity": 0.18,
        "line-blur": 6,
      },
    });
    map.addLayer({
      id: "route-line-top",
      type: "line",
      source: "route-line",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": "#DFFF00", "line-width": 4 },
    });

    // Start marker
    const startEl = document.createElement("div");
    startEl.innerHTML = `
      <div style="position:relative;width:22px;height:22px;">
        <div class="marker-pulse" style="background:#DFFF00;"></div>
        <div style="position:absolute;inset:5px;background:#DFFF00;border-radius:999px;border:2px solid #000;"></div>
      </div>`;
    const startMarker = new mapboxgl.Marker(startEl).setLngLat(route.start).addTo(map);
    map._runMarkers.push(startMarker);

    // Water stop marker at midpoint
    if (route.midpoint) {
      const waterEl = document.createElement("div");
      waterEl.innerHTML = `
        <div style="width:24px;height:24px;background:#00E5FF;border-radius:999px;
          border:2px solid #000;display:flex;align-items:center;justify-content:center;
          color:#000;font-weight:900;font-family:'Barlow Condensed';font-size:12px;">H₂O</div>`;
      const wm = new mapboxgl.Marker(waterEl).setLngLat(route.midpoint).addTo(map);
      map._runMarkers.push(wm);
    }

    // Fit bounds
    const bounds = new mapboxgl.LngLatBounds();
    route.coordinates.forEach((c) => bounds.extend(c));
    map.fitBounds(bounds, { padding: { top: 100, bottom: 220, left: 60, right: 60 }, duration: 1200 });
  }, [route, ready]);

  return (
    <div className="relative w-full h-full grain" data-testid={PANELS.map}>
      <div ref={containerRef} className="absolute inset-0" />
    </div>
  );
}
