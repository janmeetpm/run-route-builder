import { useEffect, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import { PANELS } from "@/constants/testIds";

const MAPBOX_TOKEN = process.env.REACT_APP_MAPBOX_TOKEN;
mapboxgl.accessToken = MAPBOX_TOKEN;

const CITY_CENTERS = {
  bengaluru: [77.5946, 12.9716],
  delhi: [77.209, 28.6139],
};

const ROUTE_COLOR = "#2F5D3F";
const WATER_COLOR = "#4A8FA4";

export default function RouteMap({ city, route, onMapClick }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (mapRef.current) return;
    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/light-v11",
      center: CITY_CENTERS[city] || CITY_CENTERS.bengaluru,
      zoom: 12.5,
      pitch: 20,
      attributionControl: false,
    });
    map.addControl(new mapboxgl.NavigationControl({ visualizePitch: true }), "bottom-right");
    map.on("load", () => setReady(true));
    map.on("click", (e) => {
      if (onMapClick) onMapClick([e.lngLat.lng, e.lngLat.lat]);
    });
    mapRef.current = map;
  }, []); // eslint-disable-line

  useEffect(() => {
    if (!mapRef.current || !ready) return;
    const c = CITY_CENTERS[city];
    if (c) mapRef.current.flyTo({ center: c, zoom: 12.5, duration: 1400, essential: true });
  }, [city, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    try {
      ["route-line-top", "route-glow"].forEach((id) => {
        if (map.getLayer(id)) map.removeLayer(id);
      });
      if (map.getSource("route-line")) map.removeSource("route-line");
    } catch (e) {
      console.warn("route cleanup:", e);
    }
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
        "line-color": ROUTE_COLOR,
        "line-width": 12,
        "line-opacity": 0.14,
        "line-blur": 5,
      },
    });
    map.addLayer({
      id: "route-line-top",
      type: "line",
      source: "route-line",
      layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": ROUTE_COLOR, "line-width": 3.5 },
    });

    // Start marker
    const startEl = document.createElement("div");
    startEl.innerHTML = `
      <div style="position:relative;width:22px;height:22px;">
        <div class="marker-pulse" style="background:${ROUTE_COLOR};"></div>
        <div style="position:absolute;inset:5px;background:#fff;border-radius:999px;border:2px solid ${ROUTE_COLOR};"></div>
      </div>`;
    map._runMarkers.push(new mapboxgl.Marker(startEl).setLngLat(route.start).addTo(map));

    if (route.midpoint) {
      const waterEl = document.createElement("div");
      waterEl.innerHTML = `
        <div style="width:22px;height:22px;background:#fff;border-radius:999px;
          border:2px solid ${WATER_COLOR};display:flex;align-items:center;justify-content:center;
          color:${WATER_COLOR};font-weight:800;font-family:'Bricolage Grotesque';font-size:9px;letter-spacing:-0.03em;">H₂O</div>`;
      map._runMarkers.push(new mapboxgl.Marker(waterEl).setLngLat(route.midpoint).addTo(map));
    }

    const bounds = new mapboxgl.LngLatBounds();
    route.coordinates.forEach((c) => bounds.extend(c));
    map.fitBounds(bounds, { padding: { top: 90, bottom: 200, left: 80, right: 60 }, duration: 1200 });
  }, [route, ready]);

  return (
    <div className="relative w-full h-full" data-testid={PANELS.map}>
      <div ref={containerRef} className="absolute inset-0" />
    </div>
  );
}
