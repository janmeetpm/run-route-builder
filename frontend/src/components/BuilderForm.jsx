import { useState } from "react";
import { BUILDER } from "@/constants/testIds";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Lightning, Compass, Sun, MoonStars } from "@phosphor-icons/react";

const CITIES = [
  { key: "bengaluru", label: "BENGALURU", start_lon: 77.5946, start_lat: 12.9716, start_name: "MG Road, Bengaluru" },
  { key: "delhi", label: "DELHI", start_lon: 77.209, start_lat: 28.6139, start_name: "Connaught Place, Delhi" },
];

export default function BuilderForm({ city, setCity, onGenerate, loading, customStart }) {
  const [distance, setDistance] = useState(5);
  const [pace, setPace] = useState("easy");
  const [provider, setProvider] = useState("claude");
  const [loop, setLoop] = useState(true);
  const [waterStop, setWaterStop] = useState(true);
  const [avoidHwy, setAvoidHwy] = useState(true);
  const [wellLit, setWellLit] = useState(true);
  const [startTime, setStartTime] = useState("05:30");

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
      constraints: {
        loop, water_stop: waterStop, avoid_highways: avoidHwy,
        well_lit: wellLit, start_time: startTime,
      },
    });
  };

  return (
    <form
      data-testid={BUILDER.form}
      onSubmit={(e) => { e.preventDefault(); submit(); }}
      className="space-y-6"
    >
      {/* City toggle */}
      <div>
        <Label className="font-mono text-[10px] tracking-[0.2em] text-white/50">CITY</Label>
        <div className="grid grid-cols-2 gap-2 mt-2">
          {CITIES.map((c) => (
            <button
              key={c.key}
              data-testid={c.key === "bengaluru" ? BUILDER.cityBengaluru : BUILDER.cityDelhi}
              type="button"
              onClick={() => setCity(c.key)}
              className={`font-head text-sm py-2.5 border rounded-sm transition-colors duration-200 ${
                city === c.key
                  ? "bg-[#DFFF00] text-black border-[#DFFF00]"
                  : "bg-transparent text-white/70 border-white/15 hover:bg-white/5"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>
        <div className="mt-2 font-mono text-[10px] text-white/40">
          Start: {customStart?.name || cityObj.start_name}
        </div>
      </div>

      {/* Distance */}
      <div>
        <div className="flex justify-between items-baseline mb-2">
          <Label className="font-mono text-[10px] tracking-[0.2em] text-white/50">DISTANCE</Label>
          <span className="font-head text-2xl text-[#DFFF00]">{distance} km</span>
        </div>
        <Slider
          data-testid={BUILDER.distanceSlider}
          value={[distance]}
          onValueChange={(v) => setDistance(v[0])}
          min={2}
          max={21}
          step={0.5}
          className="w-full"
        />
        <div className="flex justify-between font-mono text-[9px] text-white/30 mt-1">
          <span>2K</span><span>10K</span><span>HALF</span>
        </div>
      </div>

      {/* Pace */}
      <div>
        <Label className="font-mono text-[10px] tracking-[0.2em] text-white/50">PACE GROUP</Label>
        <div className="grid grid-cols-3 gap-2 mt-2">
          {[
            { k: "easy", label: "EASY", tid: BUILDER.paceEasy },
            { k: "tempo", label: "TEMPO", tid: BUILDER.paceTempo },
            { k: "long", label: "LONG", tid: BUILDER.paceLong },
          ].map((p) => (
            <button
              key={p.k}
              data-testid={p.tid}
              type="button"
              onClick={() => setPace(p.k)}
              className={`font-head text-xs py-2 border rounded-sm transition-colors duration-200 ${
                pace === p.k ? "bg-white text-black border-white" : "bg-transparent text-white/60 border-white/15 hover:bg-white/5"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Provider */}
      <div>
        <Label className="font-mono text-[10px] tracking-[0.2em] text-white/50">NARRATOR</Label>
        <Select value={provider} onValueChange={setProvider}>
          <SelectTrigger
            data-testid={BUILDER.providerSelect}
            className="mt-2 bg-white/5 border-white/15 rounded-sm text-white h-10 font-mono"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-[#121212] border-white/15 text-white">
            <SelectItem value="claude">CLAUDE SONNET 5</SelectItem>
            <SelectItem value="gemini">GEMINI 3.1 PRO</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Constraints */}
      <div>
        <Label className="font-mono text-[10px] tracking-[0.2em] text-white/50">CONSTRAINTS</Label>
        <div className="mt-2 space-y-2 border border-white/10 rounded-sm p-3 bg-white/5">
          <Row label="Loop (no out-and-back)" checked={loop} onChange={setLoop} tid={BUILDER.loopToggle} />
          <Row label="Water stop midway" checked={waterStop} onChange={setWaterStop} tid={BUILDER.waterStopToggle} />
          <Row label="Avoid highways" checked={avoidHwy} onChange={setAvoidHwy} tid={BUILDER.highwaysToggle} />
          <Row label="Well-lit paths" checked={wellLit} onChange={setWellLit} tid={BUILDER.wellLitToggle} />
        </div>
      </div>

      {/* Start time */}
      <div>
        <Label className="font-mono text-[10px] tracking-[0.2em] text-white/50">START TIME</Label>
        <div className="flex items-center gap-2 mt-2">
          <MoonStars size={16} className="text-white/40" />
          <input
            data-testid={BUILDER.startTime}
            type="time"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            className="bg-white/5 border border-white/15 rounded-sm px-3 py-2 font-mono text-sm text-white flex-1"
          />
          <Sun size={16} className="text-[#DFFF00]" />
        </div>
      </div>

      <Button
        data-testid={BUILDER.generateBtn}
        type="submit"
        disabled={loading}
        className="w-full h-12 bg-[#DFFF00] hover:bg-[#c9e800] text-black font-head text-base tracking-widest rounded-sm disabled:opacity-50"
      >
        <Lightning size={18} weight="fill" className="mr-2" />
        {loading ? "PLOTTING…" : "GENERATE ROUTE"}
      </Button>
    </form>
  );
}

function Row({ label, checked, onChange, tid }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-white/80">{label}</span>
      <Switch
        data-testid={tid}
        checked={checked}
        onCheckedChange={onChange}
        className="data-[state=checked]:bg-[#DFFF00]"
      />
    </div>
  );
}
