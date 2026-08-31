import { PANELS } from "@/constants/testIds";
import { MapTrifold, Mountains, Path, ShieldCheck, Drop } from "@phosphor-icons/react";

export default function NarrationPanel({ route }) {
  if (!route) return null;
  const n = route.narration || {};
  const stats = route.elev_stats || {};

  return (
    <div
      data-testid={PANELS.narration}
      className="absolute top-6 right-6 w-[380px] max-h-[70vh] overflow-y-auto
        bg-black/70 backdrop-blur-xl border border-white/20 rounded-md p-5 z-20 shadow-2xl narration-scroll"
    >
      <div className="flex items-center gap-2 mb-2">
        <div className="w-1.5 h-1.5 rounded-full bg-[#DFFF00]" />
        <span className="font-mono text-[10px] tracking-[0.2em] text-white/60">
          NARRATED • {route.provider?.toUpperCase()}
        </span>
      </div>
      <h2 className="font-head text-3xl leading-none text-white mb-3">
        {n.headline || `${route.distance_km}KM LOOP`}
      </h2>

      <div className="grid grid-cols-3 gap-2 mb-4 text-xs">
        <Stat icon={<Path size={14} />} label="DISTANCE" value={`${route.distance_km} km`} />
        <Stat icon={<Mountains size={14} />} label="ASCENT" value={`${stats.ascent_m || 0} m`} />
        <Stat icon={<Path size={14} />} label="TIME" value={fmtTime(route.duration_s)} />
      </div>

      <p className="text-[13px] leading-relaxed text-white/85 whitespace-pre-wrap">
        {n.narration}
      </p>

      {n.segments?.length > 0 && (
        <div className="mt-4 space-y-2">
          {n.segments.map((s, i) => (
            <div key={i} className="border-l-2 border-[#DFFF00] pl-3">
              <div className="flex items-baseline gap-2">
                <span className="font-head text-sm text-white">{s.label}</span>
                <span className="font-mono text-[10px] text-white/50">
                  {fmt1(s.km_start)}–{fmt1(s.km_end)} km
                </span>
              </div>
              <div className="text-xs text-white/70">{s.vibe}</div>
            </div>
          ))}
        </div>
      )}

      {n.safety_note && (
        <div className="mt-4 flex gap-2 items-start bg-white/5 border border-white/10 p-3 rounded-sm">
          <ShieldCheck size={16} className="text-[#DFFF00] mt-0.5 shrink-0" />
          <span className="text-xs text-white/80">{n.safety_note}</span>
        </div>
      )}
      {n.water_stop_pitch && (
        <div className="mt-2 flex gap-2 items-start bg-[#00E5FF]/10 border border-[#00E5FF]/30 p-3 rounded-sm">
          <Drop size={16} className="text-[#00E5FF] mt-0.5 shrink-0" />
          <span className="text-xs text-white/80">{n.water_stop_pitch}</span>
        </div>
      )}
    </div>
  );
}

function Stat({ icon, label, value }) {
  return (
    <div className="bg-white/5 border border-white/10 p-2 rounded-sm">
      <div className="flex items-center gap-1 text-white/50 mb-1">
        {icon}
        <span className="font-mono text-[9px] tracking-widest">{label}</span>
      </div>
      <div className="font-head text-lg text-white">{value}</div>
    </div>
  );
}

function fmt1(v) {
  return typeof v === "number" ? v.toFixed(1) : v;
}
function fmtTime(s) {
  if (!s) return "—";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}
