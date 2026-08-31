import { useState } from "react";
import { ArrowRight, ArrowUUpLeft, ArrowUUpRight, ArrowElbowRight, ArrowElbowLeft, Flag, CaretDown, CaretUp } from "@phosphor-icons/react";

// ORS step type codes → icon
const ICON = {
  0: ArrowElbowLeft, // Left
  1: ArrowElbowRight, // Right
  2: ArrowUUpLeft, // Sharp left
  3: ArrowUUpRight, // Sharp right
  4: ArrowElbowLeft, // Slight left
  5: ArrowElbowRight, // Slight right
  6: ArrowRight, // Straight
  10: Flag, // Arrive
  11: Flag, // Depart
};

const NAMES = {
  0: "LEFT",
  1: "RIGHT",
  2: "SHARP LEFT",
  3: "SHARP RIGHT",
  4: "SLIGHT LEFT",
  5: "SLIGHT RIGHT",
  6: "STRAIGHT",
  7: "ROUNDABOUT",
  8: "EXIT",
  10: "ARRIVE",
  11: "DEPART",
};

export default function TurnByTurn({ steps }) {
  const [open, setOpen] = useState(true);
  if (!steps?.length) return null;

  return (
    <div
      data-testid="turn-by-turn"
      className="absolute top-6 left-6 w-[300px] max-h-[70vh] flex flex-col
        bg-black/70 backdrop-blur-xl border border-white/20 rounded-md z-20 shadow-2xl overflow-hidden"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-4 py-3 border-b border-white/10 bg-white/5 hover:bg-white/10 transition-colors"
      >
        <div className="w-1.5 h-1.5 rounded-full bg-[#DFFF00]" />
        <span className="font-mono text-[10px] tracking-[0.2em] text-white/70 flex-1 text-left">
          TURN-BY-TURN · {steps.length} STEPS
        </span>
        {open ? <CaretUp size={12} className="text-white/50" /> : <CaretDown size={12} className="text-white/50" />}
      </button>
      {open && (
        <div className="flex-1 overflow-y-auto no-scrollbar divide-y divide-white/5">
          {steps.map((s, i) => {
            const Icon = ICON[s.type] || ArrowRight;
            const name = NAMES[s.type] || "MOVE";
            const dist = s.distance_m || 0;
            return (
              <div key={i} className="px-4 py-2.5 flex items-start gap-3 hover:bg-white/5 transition-colors">
                <div className="w-8 h-8 shrink-0 flex items-center justify-center border border-white/15 rounded-sm bg-black">
                  <Icon size={16} className="text-[#DFFF00]" weight="bold" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-mono text-[9px] tracking-[0.2em] text-white/50">{name}</div>
                  <div className="text-[12px] text-white/90 leading-snug truncate" title={s.instruction}>
                    {s.instruction}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="font-head text-sm text-white leading-none">
                    {dist < 1000 ? `${Math.round(dist)}m` : `${(dist / 1000).toFixed(2)}km`}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
