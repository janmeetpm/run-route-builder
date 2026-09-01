import { PANELS } from "@/constants/testIds";
import { Mountains, Path, ShieldCheck, Drop } from "@phosphor-icons/react";

export default function NarrationPanel({ route }) {
  if (!route) return null;
  const n = route.narration || {};
  const stats = route.elev_stats || {};

  return (
    <div
      data-testid={PANELS.narration}
      className="absolute top-6 right-6 w-[380px] max-h-[70vh] overflow-y-auto
        bg-white/95 backdrop-blur-sm border border-[color:var(--line-strong)] rounded-lg p-6 z-20
        shadow-[0_20px_50px_-20px_rgba(26,34,28,0.25)] narration-scroll"
    >
      <div className="mut-caps mb-3">Narrated · {route.provider}</div>
      <h2 className="font-display text-[34px] leading-[0.95] text-[color:var(--ink)] mb-5">
        {n.headline || `${route.distance_km} km loop`}
      </h2>

      <div className="grid grid-cols-3 gap-3 mb-5">
        <Stat icon={<Path size={12} />} label="Distance" value={`${route.distance_km}`} unit="km" />
        <Stat icon={<Mountains size={12} />} label="Ascent" value={`${stats.ascent_m || 0}`} unit="m" />
        <Stat icon={<Path size={12} />} label="Time" value={fmtTime(route.duration_s)} />
      </div>

      <p className="text-[14px] leading-relaxed text-[color:var(--ink-soft)] whitespace-pre-wrap">
        {n.narration}
      </p>

      {n.segments?.length > 0 && (
        <div className="mt-5 pt-5 border-t border-[color:var(--line)] space-y-3">
          {n.segments.map((s, i) => (
            <div key={i}>
              <div className="flex items-baseline gap-2">
                <span className="font-head text-[15px] text-[color:var(--ink)]">{s.label}</span>
                <span className="font-mono text-[10px] text-[color:var(--ink-mute)]">
                  {fmt1(s.km_start)}–{fmt1(s.km_end)} km
                </span>
              </div>
              <div className="text-[13px] text-[color:var(--ink-soft)] mt-0.5">{s.vibe}</div>
            </div>
          ))}
        </div>
      )}

      {n.safety_note && (
        <div className="mt-5 flex gap-2 items-start">
          <ShieldCheck size={16} className="text-[color:var(--forest)] mt-0.5 shrink-0" />
          <span className="text-[13px] text-[color:var(--ink-soft)]">{n.safety_note}</span>
        </div>
      )}
      {n.water_stop_pitch && (
        <div className="mt-2 flex gap-2 items-start">
          <Drop size={16} className="text-[color:var(--water)] mt-0.5 shrink-0" />
          <span className="text-[13px] text-[color:var(--ink-soft)]">{n.water_stop_pitch}</span>
        </div>
      )}
    </div>
  );
}

function Stat({ icon, label, value, unit }) {
  return (
    <div>
      <div className="flex items-center gap-1 text-[color:var(--ink-mute)]">
        {icon}
        <span className="mut-caps text-[9px]">{label}</span>
      </div>
      <div className="font-display text-[22px] leading-none text-[color:var(--ink)] mt-1">
        {value}
        {unit && <span className="text-[13px] text-[color:var(--ink-mute)] ml-1">{unit}</span>}
      </div>
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
  return `${Math.floor(m / 60)}h${m % 60}`;
}
