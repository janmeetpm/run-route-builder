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
import { PANELS, BUILDER } from "@/constants/testIds";
import { Compass, GearSix, Barbell, FloppyDisk, ShareNetwork } from "@phosphor-icons/react";
import useSWR from "swr";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fetcher = (url) => axios.get(url).then((r) => r.data);

export default function Home() {
  const [city, setCity] = useState("bengaluru");
  const [route, setRoute] = useState(null);
  const [loading, setLoading] = useState(false);
  const [customStart, setCustomStart] = useState(null);
  const [tab, setTab] = useState("builder");

  const { data: discovery } = useSWR(`${API}/discovery?city=${city}`, fetcher);

  const generate = async (payload) => {
    setLoading(true);
    setRoute(null);
    toast.loading("LLM guessing route… then handing to real map API.", { id: "gen" });
    try {
      const { data } = await axios.post(`${API}/routes/generate`, payload, { timeout: 90000 });
      setRoute(data);
      toast.success(`Route ready • ${data.distance_km} km`, { id: "gen" });
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
      });
      toast.success("Saved to your locker.");
    } catch (e) {
      toast.error("Could not save route.");
    }
  };

  return (
    <div className="h-screen w-screen flex bg-[#0a0a0a] text-white overflow-hidden">
      {/* SIDEBAR */}
      <aside className="w-[440px] shrink-0 h-full border-r border-white/10 flex flex-col relative grain">
        <div className="relative z-10 px-6 pt-6 pb-4 border-b border-white/10">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-6 h-6 bg-[#DFFF00] flex items-center justify-center rounded-sm">
              <Barbell size={14} weight="bold" className="text-black" />
            </div>
            <span className="font-head text-lg text-white">TRAILSCRIBE</span>
            <span className="ml-auto font-mono text-[9px] tracking-widest text-white/40">
              v0.1 · 05:30 AGENT
            </span>
          </div>
          <p className="text-xs text-white/60 leading-relaxed">
            An LLM guesses your loop. The map API fixes what geometry it got wrong. You get a route
            that <em>actually</em> closes — and a log of every failure.
          </p>
        </div>

        <div className="relative z-10 flex-1 overflow-y-auto no-scrollbar px-6 py-5">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList className="grid grid-cols-2 bg-white/5 border border-white/10 rounded-sm p-1 mb-5">
              <TabsTrigger
                data-testid={PANELS.builderTab}
                value="builder"
                className="rounded-sm font-head text-xs tracking-widest data-[state=active]:bg-[#DFFF00] data-[state=active]:text-black"
              >
                <GearSix size={13} className="mr-1.5" /> BUILDER
              </TabsTrigger>
              <TabsTrigger
                data-testid={PANELS.discoveryTab}
                value="discover"
                className="rounded-sm font-head text-xs tracking-widest data-[state=active]:bg-[#DFFF00] data-[state=active]:text-black"
              >
                <Compass size={13} className="mr-1.5" /> DISCOVER
              </TabsTrigger>
            </TabsList>

            <TabsContent value="builder">
              <BuilderForm
                city={city}
                setCity={setCity}
                onGenerate={generate}
                loading={loading}
                customStart={customStart}
              />
            </TabsContent>

            <TabsContent value="discover">
              <div className="mb-3 font-mono text-[10px] tracking-[0.25em] text-white/50">
                CURATED · {city.toUpperCase()}
              </div>
              <DiscoveryGrid routes={discovery?.routes} onPick={pickDiscovery} />
            </TabsContent>
          </Tabs>

          <div className="mt-6">
            <FailureLog entries={route?.failure_log} llmGuess={route?.llm_guess} />
          </div>
        </div>

        {route && (
          <div className="relative z-10 border-t border-white/10 bg-black/60 backdrop-blur-md p-4 flex gap-2">
            <Button
              data-testid={BUILDER.saveBtn}
              onClick={saveRoute}
              className="flex-1 rounded-sm bg-[#DFFF00] hover:bg-[#c9e800] text-black font-head tracking-widest text-xs h-10"
            >
              <FloppyDisk size={13} className="mr-1.5" weight="fill" /> SAVE
            </Button>
            <Button
              onClick={() => {
                navigator.clipboard.writeText(JSON.stringify(route.coordinates));
                toast.success("GPX-ready coords copied.");
              }}
              variant="outline"
              className="flex-1 rounded-sm border-white/20 bg-transparent hover:bg-white/5 text-white font-head tracking-widest text-xs h-10"
            >
              <ShareNetwork size={13} className="mr-1.5" /> COPY GPS
            </Button>
          </div>
        )}
      </aside>

      {/* MAP AREA */}
      <main className="flex-1 relative h-full">
        <RouteMap city={city} route={route} onMapClick={onMapClick} />
        {route && <NarrationPanel route={route} />}
        {route && <ElevationProfile route={route} />}
        {!route && (
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-center pointer-events-none z-10">
            <div className="font-head text-5xl text-white/80 tracking-widest">READY TO RUN</div>
            <div className="font-mono text-[11px] text-white/50 mt-2 tracking-[0.3em]">
              CLICK THE MAP TO SET A CUSTOM START · OR USE THE BUILDER
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
