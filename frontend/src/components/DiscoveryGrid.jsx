import { PANELS } from "@/constants/testIds";
import { Users, Mountains } from "@phosphor-icons/react";

const IMG = {
  Bengaluru: "https://images.unsplash.com/photo-1706241137081-4b5e0f038d88",
  Delhi: "https://images.unsplash.com/photo-1695667424131-a9680e0307ee",
};

export default function DiscoveryGrid({ routes, onPick }) {
  if (!routes?.length) {
    return <div className="text-[color:var(--ink-mute)] text-sm p-2">No curated routes for this city yet.</div>;
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {routes.map((r) => (
        <button
          data-testid={PANELS.routeCard}
          key={r.id}
          onClick={() => onPick(r)}
          className="group text-left border border-[color:var(--line-strong)] bg-white rounded-lg overflow-hidden
            hover:-translate-y-0.5 hover:border-[color:var(--forest)] transition-all duration-300"
        >
          <div className="relative h-24">
            <img
              src={`${IMG[r.city]}?auto=format&w=600&q=60`}
              alt={r.name}
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[color:var(--ink)]/70 via-transparent to-transparent" />
            <div className="absolute bottom-2 left-3 right-3">
              <div className="font-head text-[15px] text-white leading-tight">{r.name}</div>
            </div>
          </div>
          <div className="p-3 space-y-2">
            <div className="flex items-center justify-between font-mono text-[10px] text-[color:var(--ink-mute)]">
              <span className="text-[color:var(--forest)] font-display text-[13px]">{r.distance_km} km</span>
              <span className="flex items-center gap-1"><Mountains size={10} /> {r.elevation_gain_m}m</span>
              <span className="flex items-center gap-1"><Users size={10} /> {r.athletes_this_week}</span>
            </div>
            <p className="text-[12px] text-[color:var(--ink-soft)] line-clamp-2 leading-relaxed">{r.vibe}</p>
          </div>
        </button>
      ))}
    </div>
  );
}
