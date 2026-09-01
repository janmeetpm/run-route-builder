import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import BuilderForm from "@/components/BuilderForm";
import DiscoveryGrid from "@/components/DiscoveryGrid";
import RouteMap from "@/components/RouteMap";
import NarrationPanel from "@/components/NarrationPanel";
import FailureLog from "@/components/FailureLog";
import ElevationProfile from "@/components/ElevationProfile";
import TurnByTurn from "@/components/TurnByTurn";
import WeatherStrip from "@/components/WeatherStrip";
import StravaConnect from "@/components/StravaConnect";
import StravaSafety from "@/components/StravaSafety";
import FriendOverlap from "@/components/FriendOverlap";
import WeeklyDigest from "@/components/WeeklyDigest";
import { PANELS, BUILDER } from "@/constants/testIds";
import { Compass, GearSix, Waveform, FloppyDisk, DownloadSimple, ArrowSquareOut } from "@phosphor-icons/react";
import useSWR from "swr";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fetcher = (url) => axios.get(url).then((r) => r.data);

export default function Home() {
  const [city, setCityState] = useState("bengaluru");
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [customStart, setCustomStart] = useState(null);
  const [tab, setTab] = useState("builder");
  const [strava, setStrava] = useState({ connected: false });

  const setCity = (next) => {
    setCityState(next);
    setCustomStart(null);
    setRoute(null);
  };

  const { data: discovery } = useSWR(`${API}/discovery?city=${city}`, fetcher);

  const generate = async (payload) => {
    setLoading(true);
    setRoute(null);
    toast.loading("LLM guessing route… then handing to the map API.", { id: "gen" });
    try {
      const { data } = await axios.post(`${API}/routes/generate`, payload, { timeout: 90000 });
      setRoute(data);
      toast.success(`Route ready · ${data.distance_km} km`, { id: "gen" });
      setTab("signals"); // reveal the signals panel after generation
    } catch (e) {
      toast.error(e.response?.data?.detail || "Route generation failed", { id: "gen" });
    } finally {
      setLoading(false);
    }
  };

  const pickDiscovery = (r) => {
    setCustomStart({ lon: r.start.lon, lat: r.start.lat, name: r.start.name });
    setTab("builder");
    toast.success(`Loaded ${r.name}. Adjust and generate.`);
  };

  const onMapClick = (lonlat) => {
    setCustomStart({ lon: lonlat[0], lat: lonlat[1], name: `Custom pin (${lonlat[0].toFixed(4)}, ${lonlat[1].toFixed(4)})` });
    toast.success("Custom start pinned — tap Generate.");
  };

  const saveRoute = async () => {
    if (!route) return;
    try {
      await axios.post(`${API}/routes/save`, {
        name: route.narration?.headline || `${route.distance_km}km loop`,
        city: city.charAt(0).toUpperCase() + city.slice(1),
        distance_km: route.distance_km,
        ascent_m: route.elev_stats?.ascent_m || 0,
        provider: route.provider,
        coordinates: route.coordinates,
        elevations: route.elevations,
        cumulative_distance_m: route.cumulative_distance_m,
        narration: route.narration,
        failure_log: route.failure_log,
        midpoint: route.midpoint,
        weather: route.weather,
      });
      toast.success("Saved.");
    } catch {
      toast.error("Could not save route.");
    }
  };

  const downloadGpx = async () => {
    if (!route) return;
    try {
      const resp = await axios.post(
        `${API}/routes/gpx`,
        {
          name: route.narration?.headline || `Trailscribe ${route.distance_km}km`,
          coordinates: route.coordinates,
          elevations: route.elevations,
        },
        { responseType: "blob" }
      );
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      const safe = (route.narration?.headline || `route-${route.distance_km}km`)
        .replace(/[^a-z0-9-]+/gi, "-").toLowerCase();
      a.download = `${safe}.gpx`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("GPX downloaded.");
    } catch {
      toast.error("Could not build GPX.");
    }
  };

  const openInStravaBuilder = () => {
    if (!route) return;
    navigator.clipboard.writeText(JSON.stringify(route.coordinates));
    window.open("https://www.strava.com/routes/new", "_blank", "noopener");
    toast.success("Strava Route Builder opened. Import your GPX.");
  };

  const hasRoute = !!route;

  return (
    <div className="h-screen w-screen flex bg-[color:var(--bg)] text-[color:var(--ink)] overflow-hidden">
      {/* SIDEBAR */}
      <aside className="w-[420px] shrink-0 h-full border-r border-[color:var(--line)] bg-[color:var(--bg)] flex flex-col relative paper">
        {/* Header */}
        <div className="relative z-10 px-8 pt-8 pb-5">
          <div className="flex items-baseline justify-between mb-1">
            <span className="font-display text-2xl tracking-tight text-[color:var(--ink)]">Trailscribe</span>
            <span className="mut-caps text-[9px]">05:30 · v0.2</span>
          </div>
          <p className="text-[13px] text-[color:var(--ink-soft)] leading-relaxed mt-2">
            An LLM guesses your loop. The map fixes what the LLM got wrong. You keep a log of every failure.
          </p>
          <div className="mt-4"><StravaConnect onConnected={setStrava} /></div>
        </div>

        {/* Tabs */}
        <div className="relative z-10 px-8">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="grid grid-cols-3 bg-transparent border-b border-[color:var(--line)] rounded-none p-0 h-auto gap-6 justify-start">
              <TabsTrigger
                data-testid={PANELS.builderTab}
                value="builder"
                className="rounded-none border-b-2 border-transparent px-0 pb-3 font-head text-[12px] text-[color:var(--ink-mute)] data-[state=active]:border-[color:var(--forest)] data-[state=active]:text-[color:var(--ink)] data-[state=active]:bg-transparent data-[state=active]:shadow-none"
              >
                <GearSix size={12} className="mr-1.5" /> Builder
              </TabsTrigger>
              <TabsTrigger
                data-testid={PANELS.discoveryTab}
                value="discover"
                className="rounded-none border-b-2 border-transparent px-0 pb-3 font-head text-[12px] text-[color:var(--ink-mute)] data-[state=active]:border-[color:var(--forest)] data-[state=active]:text-[color:var(--ink)] data-[state=active]:bg-transparent data-[state=active]:shadow-none"
              >
                <Compass size={12} className="mr-1.5" /> Discover
              </TabsTrigger>
              <TabsTrigger
                data-testid="signals-tab"
                value="signals"
                disabled={!hasRoute}
                className="rounded-none border-b-2 border-transparent px-0 pb-3 font-head text-[12px] text-[color:var(--ink-mute)] data-[state=active]:border-[color:var(--forest)] data-[state=active]:text-[color:var(--ink)] data-[state=active]:bg-transparent data-[state=active]:shadow-none disabled:opacity-40"
              >
                <Waveform size={12} className="mr-1.5" /> Signals
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        {/* Tab content */}
        <div className="relative z-10 flex-1 overflow-y-auto no-scrollbar px-8 py-6 pb-40">
          <Tabs value={tab}>
            <TabsContent value="builder" className="mt-0">
              <BuilderForm
                city={city}
                setCity={setCity}
                onGenerate={generate}
                loading={loading}
                customStart={customStart}
              />
            </TabsContent>

            <TabsContent value="discover" className="mt-0 space-y-4">
              <div className="mut-caps">Curated · {city}</div>
              <DiscoveryGrid routes={discovery?.routes} onPick={pickDiscovery} />
              <div className="pt-2">
                <WeeklyDigest city={city} />
              </div>
            </TabsContent>

            <TabsContent value="signals" className="mt-0 space-y-4">
              {!hasRoute && (
                <div className="text-[13px] text-[color:var(--ink-mute)]">
                  Generate a route first — signals appear once we have geometry.
                </div>
              )}
              {hasRoute && (
                <>
                  <FailureLog entries={route.failure_log} llmGuess={route.llm_guess} />
                  {strava.connected && <StravaSafety route={route} stravaConnected={strava.connected} />}
                  {strava.connected && <FriendOverlap route={route} stravaConnected={strava.connected} />}
                  {!strava.connected && (
                    <div className="border border-dashed border-[color:var(--line-strong)] rounded-lg p-4 text-[12px] text-[color:var(--ink-mute)] italic">
                      Connect Strava above to see the “Safe & Tested” score and your own history overlap for this loop.
                    </div>
                  )}
                </>
              )}
            </TabsContent>
          </Tabs>
        </div>

        {/* Sticky actions */}
        {hasRoute && (
          <div className="relative z-10 border-t border-[color:var(--line)] bg-[color:var(--bg)]/95 backdrop-blur-sm px-8 py-4 space-y-2">
            <div className="flex gap-2">
              <Button
                data-testid={BUILDER.saveBtn}
                onClick={saveRoute}
                className="flex-1 rounded-md bg-[color:var(--forest)] hover:bg-[color:var(--forest-soft)] text-white font-head text-xs h-10"
              >
                <FloppyDisk size={13} className="mr-1.5" weight="fill" /> Save
              </Button>
              <Button
                data-testid="gpx-download-btn"
                onClick={downloadGpx}
                variant="outline"
                className="flex-1 rounded-md border-[color:var(--line-strong)] bg-transparent hover:bg-[color:var(--surface-2)] text-[color:var(--ink)] font-head text-xs h-10"
              >
                <DownloadSimple size={13} className="mr-1.5" /> GPX
              </Button>
            </div>
            <Button
              data-testid="push-to-strava-btn"
              onClick={openInStravaBuilder}
              variant="outline"
              className="w-full rounded-md border-[color:var(--strava-40)] bg-transparent hover:bg-[color:var(--strava-08)] text-[color:var(--strava)] font-head text-xs h-9"
            >
              <ArrowSquareOut size={12} className="mr-1.5" /> Open in Strava Route Builder
            </Button>
          </div>
        )}
      </aside>

      {/* MAP AREA */}
      <main className="flex-1 relative h-full bg-[color:var(--bg-2)]">
        <RouteMap city={city} route={route} onMapClick={onMapClick} />
        {hasRoute && <TurnByTurn steps={route.steps} />}
        {hasRoute && <NarrationPanel route={route} />}
        {hasRoute && <WeatherStrip weather={route.weather} />}
        {hasRoute && <ElevationProfile route={route} />}
        {!hasRoute && (
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none z-10">
            <div className="font-display text-6xl text-[color:var(--ink)]/85 tracking-tight leading-none">
              Ready to run.
            </div>
            <div className="mut-caps mt-4">Click the map to set a custom start · or use the builder</div>
          </div>
        )}
      </main>
    </div>
  );
}
