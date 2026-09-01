import { useState } from "react";
import { ArrowRight, ArrowUUpLeft, ArrowUUpRight, ArrowElbowRight, ArrowElbowLeft, Flag, CaretDown, CaretUp } from "@phosphor-icons/react";

const ICON = {
  0: ArrowElbowLeft, 1: ArrowElbowRight,
  2: ArrowUUpLeft, 3: ArrowUUpRight,
  4: ArrowElbowLeft, 5: ArrowElbowRight,
  6: ArrowRight, 10: Flag, 11: Flag,
};

const NAMES = {
  0: "Left", 1: "Right", 2: "Sharp left", 3: "Sharp right",
  4: "Slight left", 5: "Slight right", 6: "Straight",
  7: "Roundabout", 8: "Exit", 10: "Arrive", 11: "Depart",
};

export default function TurnByTurn({ steps }) {
  const [open, setOpen] = useState(false);
  if (!steps?.length) return null;

  return (
    <div
      data-testid="turn-by-turn"
      className="absolute top-6 left-6 w-[280px] flex flex-col
        bg-white/95 backdrop-blur-sm border border-[color:var(--line-strong)] rounded-lg z-20
        shadow-[0_10px_30px_-15px_rgba(26,34,28,0.25)] overflow-hidden"
      style={{ maxHeight: open ? "60vh" : "44px" }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-4 py-3 hover:bg-[color:var(--surface-2)] transition-colors"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-[color:var(--forest)]" />
        <span className="mut-caps text-[9px] flex-1 text-left">
          Turn-by-turn · {steps.length} steps
        </span>
        {open ? <CaretUp size={12} /> : <CaretDown size={12} />}
      </button>
      {open && (
        <div className="flex-1 overflow-y-auto no-scrollbar divide-y divide-[color:var(--line)]">
          {steps.map((s, i) => {
            const Icon = ICON[s.type] || ArrowRight;
            const name = NAMES[s.type] || "Move";
            const dist = s.distance_m || 0;
            return (
              <div key={i} className="px-4 py-2.5 flex items-start gap-3 hover:bg-[color:var(--surface-2)] transition-colors">
                <div className="w-7 h-7 shrink-0 flex items-center justify-center border border-[color:var(--line-strong)] rounded-md">
                  <Icon size={14} className="text-[color:var(--forest)]" weight="bold" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="mut-caps text-[9px]">{name}</div>
                  <div className="text-[12px] text-[color:var(--ink)] leading-snug truncate" title={s.instruction}>
                    {s.instruction}
                  </div>
                </div>
                <div className="font-display text-sm text-[color:var(--ink)] shrink-0 leading-none pt-1">
                  {dist < 1000 ? `${Math.round(dist)}m` : `${(dist / 1000).toFixed(2)}km`}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
