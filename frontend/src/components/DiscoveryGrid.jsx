import { PANELS } from "@/constants/testIds";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Lightning, MapPin, Mountains, Users } from "@phosphor-icons/react";

const IMG = {
  Bengaluru: "https://images.unsplash.com/photo-1706241137081-4b5e0f038d88",
  Delhi: "https://images.unsplash.com/photo-1695667424131-a9680e0307ee",
};

export default function DiscoveryGrid({ routes, onPick }) {
  if (!routes?.length) {
    return <div className="text-white/50 text-sm p-4">No curated routes for this city yet.</div>;
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {routes.map((r) => (
        <button
          data-testid={PANELS.routeCard}
          key={r.id}
          onClick={() => onPick(r)}
          className="group text-left border border-white/10 bg-[#121212] rounded-sm overflow-hidden
            hover:-translate-y-1 hover:bg-white/5 transition-transform duration-300"
        >
          <div className="relative h-24">
            <img
              src={`${IMG[r.city]}?auto=format&w=600&q=60`}
              alt={r.name}
              className="w-full h-full object-cover opacity-70 group-hover:opacity-100 transition-opacity duration-300"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent" />
            <div className="absolute bottom-2 left-2 right-2">
              <div className="font-head text-lg text-white leading-tight">{r.name}</div>
              <div className="flex items-center gap-1 text-[10px] text-white/70 font-mono">
                <MapPin size={10} /> {r.start.name}
              </div>
            </div>
          </div>
          <div className="p-3 space-y-2">
            <div className="flex items-center justify-between font-mono text-[11px]">
              <span className="text-[#DFFF00]">{r.distance_km} km</span>
              <span className="text-white/60 flex items-center gap-1">
                <Mountains size={11} /> {r.elevation_gain_m}m
              </span>
              <span className="text-white/60 flex items-center gap-1">
                <Users size={11} /> {r.athletes_this_week}
              </span>
            </div>
            <p className="text-xs text-white/70 line-clamp-2">{r.vibe}</p>
            <div className="flex flex-wrap gap-1">
              {r.tags.slice(0, 3).map((t) => (
                <Badge
                  key={t}
                  variant="outline"
                  className="rounded-none border-white/15 text-[9px] text-white/70 font-mono uppercase tracking-wider bg-transparent px-1.5 py-0"
                >
                  {t}
                </Badge>
              ))}
            </div>
          </div>
        </button>
      ))}
    </div>
  );
}
