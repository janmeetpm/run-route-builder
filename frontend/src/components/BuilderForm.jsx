import { useState } from "react";
import { BUILDER } from "@/constants/testIds";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Lightning, Sun, MoonStars } from "@phosphor-icons/react";

const CITIES = [
  { key: "bengaluru", label: "Bengaluru", start_lon: 77.5946, start_lat: 12.9716, start_name: "MG Road, Bengaluru" },
  { key: "delhi", label: "Delhi", start_lon: 77.209, start_lat: 28.6139, start_name: "Connaught Place, Delhi" },
];

export default function BuilderForm({ city, setCity, onGenerate, loading, customStart, stravaConnected }) {
  const [distance, setDistance] = useState(5);
  const [pace, setPace] = useState("easy");
  const [provider, setProvider] = useState("claude");
  const [loop, setLoop] = useState(true);
  const [waterStop, setWaterStop] = useState(true);
  const [avoidHwy, setAvoidHwy] = useState(true);
  const [wellLit, setWellLit] = useState(true);
  const [startTime, setStartTime] = useState("05:30");
  const [useStravaPaths, setUseStravaPaths] = useState(false);

  const cityObj = CITIES.find((c) => c.key === city) || CITIES[0];

  const submit = () => {
    const s = customStart || { lon: cityObj.start_lon, lat: cityObj.start_lat, name: cityObj.start_name };
    onGenerate({
      start_name: s.name,
      start_lon: s.lon,
      start_lat: s.lat,
      distance_km: distance,
      pace_group: pace,
      provider,
      constraints: { loop, water_stop: waterStop, avoid_highways: avoidHwy, well_lit: wellLit, start_time: startTime },
    }, { useStravaPaths: useStravaPaths && stravaConnected });
  };

  return (
    <form
      data-testid={BUILDER.form}
      onSubmit={(e) => { e.preventDefault(); submit(); }}
      className="space-y-7"
    >
      {/* City */}
      <div>
        <div className="mut-caps mb-3">City</div>
        <div className="grid grid-cols-2 gap-2">
          {CITIES.map((c) => (
            <button
              key={c.key}
              data-testid={c.key === "bengaluru" ? BUILDER.cityBengaluru : BUILDER.cityDelhi}
              type="button"
              onClick={() => setCity(c.key)}
              className={`font-head text-sm py-2.5 border rounded-md transition-colors duration-200 ${
                city === c.key
                  ? "bg-[color:var(--forest)] text-white border-[color:var(--forest)]"
                  : "bg-transparent text-[color:var(--ink-soft)] border-[color:var(--line-strong)] hover:bg-[color:var(--surface-2)]"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
        <div className="mt-2 font-mono text-[10px] text-[color:var(--ink-mute)]">
          {customStart?.name || cityObj.start_name}
        </div>
      </div>

      {/* Distance */}
      <div>
        <div className="flex justify-between items-baseline mb-3">
          <div className="mut-caps">Distance</div>
          <span className="font-display text-3xl text-[color:var(--ink)]">
            {distance}<span className="text-sm text-[color:var(--ink-mute)] ml-1">km</span>
          </span>
        </div>
        <Slider
          data-testid={BUILDER.distanceSlider}
          value={[distance]}
          onValueChange={(v) => setDistance(v[0])}
          min={2}
          max={21}
          step={0.5}
        />
        <div className="flex justify-between font-mono text-[9px] text-[color:var(--ink-mute)] mt-1.5">
          <span>2k</span><span>10k</span><span>half</span>
        </div>
      </div>

      {/* Pace */}
      <div>
        <div className="mut-caps mb-3">Pace</div>
        <div className="grid grid-cols-3 gap-2">
          {[
            { k: "easy", tid: BUILDER.paceEasy },
            { k: "tempo", tid: BUILDER.paceTempo },
            { k: "long", tid: BUILDER.paceLong },
          ].map((p) => (
            <button
              key={p.k}
              data-testid={p.tid}
              type="button"
              onClick={() => setPace(p.k)}
              className={`font-head text-xs py-2 border rounded-md transition-colors duration-200 capitalize ${
                pace === p.k
                  ? "bg-[color:var(--ink)] text-white border-[color:var(--ink)]"
                  : "bg-transparent text-[color:var(--ink-soft)] border-[color:var(--line-strong)] hover:bg-[color:var(--surface-2)]"
              }`}
            >
              {p.k}
            </button>
          ))}
        </div>
      </div>

      {/* Provider */}
      <div>
        <div className="mut-caps mb-3">Narrator</div>
        <Select value={provider} onValueChange={setProvider}>
          <SelectTrigger
            data-testid={BUILDER.providerSelect}
            className="bg-white border-[color:var(--line-strong)] rounded-md text-[color:var(--ink)] h-10"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-white border-[color:var(--line-strong)]">
            <SelectItem value="claude">Claude Sonnet 5</SelectItem>
            <SelectItem value="gemini">Gemini 3.1 Pro</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Constraints */}
      <div>
        <div className="mut-caps mb-3">Constraints</div>
        <div className="space-y-3">
          <Row label="Loop (no out-and-back)" checked={loop} onChange={setLoop} tid={BUILDER.loopToggle} />
          <Row label="Water stop midway" checked={waterStop} onChange={setWaterStop} tid={BUILDER.waterStopToggle} />
          <Row label="Avoid highways" checked={avoidHwy} onChange={setAvoidHwy} tid={BUILDER.highwaysToggle} />
          <Row label="Well-lit paths" checked={wellLit} onChange={setWellLit} tid={BUILDER.wellLitToggle} />
        </div>
      </div>

      {/* Start time */}
      <div>
        <div className="mut-caps mb-3">Start time</div>
        <div className="flex items-center gap-3">
          <MoonStars size={16} className="text-[color:var(--ink-mute)]" />
          <input
            data-testid={BUILDER.startTime}
            type="time"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            className="bg-white border border-[color:var(--line-strong)] rounded-md px-3 py-2 font-mono text-sm text-[color:var(--ink)] flex-1"
          />
          <Sun size={16} className="text-[color:var(--sun)]" />
        </div>
      </div>

      {/* Strava-driven routing */}
      {stravaConnected && (
        <div className="border border-[color:var(--strava-40)] rounded-md p-3 bg-[color:var(--strava-08)]">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-head text-[13px] text-[color:var(--ink)]">Route through popular Strava paths</div>
              <div className="text-[11px] text-[color:var(--ink-mute)] mt-0.5">Threads your loop through the most-run segments nearby.</div>
            </div>
            <Switch
              data-testid="use-strava-paths"
              checked={useStravaPaths}
              onCheckedChange={setUseStravaPaths}
              className="data-[state=checked]:bg-[color:var(--strava)]"
            />
          </div>
        </div>
      )}

      <Button
        data-testid={BUILDER.generateBtn}
        type="submit"
        disabled={loading}
        className="w-full h-12 bg-[color:var(--forest)] hover:bg-[color:var(--forest-soft)] text-white font-head text-sm rounded-md disabled:opacity-50"
      >
        <Lightning size={16} weight="fill" className="mr-2" />
        {loading ? "Plotting…" : "Generate route"}
      </Button>
    </form>
  );
}

function Row({ label, checked, onChange, tid }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[13px] text-[color:var(--ink-soft)]">{label}</span>
      <Switch
        data-testid={tid}
        checked={checked}
        onCheckedChange={onChange}
        className="data-[state=checked]:bg-[color:var(--forest)]"
      />
    </div>
  );
}
