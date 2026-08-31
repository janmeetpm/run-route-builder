import { PANELS } from "@/constants/testIds";
import { Terminal, WarningOctagon, CheckCircle, Info } from "@phosphor-icons/react";

const LEVEL = {
  info: { color: "text-white/70", tag: "INFO", icon: <Info size={12} /> },
  success: { color: "text-[#DFFF00]", tag: "OK  ", icon: <CheckCircle size={12} /> },
  warn: { color: "text-amber-400", tag: "WARN", icon: <WarningOctagon size={12} /> },
  error: { color: "text-[#FF3B30]", tag: "FAIL", icon: <WarningOctagon size={12} /> },
};

export default function FailureLog({ entries, llmGuess }) {
  return (
    <div
      data-testid={PANELS.failureLog}
      className="border border-[#FF3B30]/40 bg-black rounded-sm"
    >
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/10 bg-[#FF3B30]/10">
        <Terminal size={14} className="text-[#FF3B30]" />
        <span className="font-mono text-[10px] tracking-[0.25em] text-white/70">
          FAILURE_LOG / LLM_vs_MAP_API
        </span>
      </div>
      <div className="p-3 font-mono text-[11px] leading-relaxed space-y-1.5 max-h-[220px] overflow-y-auto no-scrollbar">
        {llmGuess && (
          <div className="text-white/40 border-l-2 border-white/20 pl-2 pb-1 mb-1">
            <span className="text-white/60">llm.reasoning:</span> "{llmGuess.reasoning}"
            <div>
              <span className="text-white/60">llm.est_km:</span> {llmGuess.estimated_distance_km}
              {"  "}
              <span className="text-white/60">llm.err:</span>{" "}
              <span className={llmGuess.distance_error_pct > 15 ? "text-[#FF3B30]" : "text-[#DFFF00]"}>
                {llmGuess.distance_error_pct}%
              </span>
            </div>
          </div>
        )}
        {(entries || []).map((e, i) => {
          const l = LEVEL[e.level] || LEVEL.info;
          return (
            <div key={i} className={`flex items-start gap-2 ${l.color}`}>
              <span className="mt-0.5">{l.icon}</span>
              <div className="flex-1">
                <span className="text-white/40">[{e.stage}]</span>{" "}
                <span>{e.message}</span>
              </div>
            </div>
          );
        })}
        {!entries?.length && (
          <div className="text-white/40">// no route generated yet — build one on the right.</div>
        )}
      </div>
    </div>
  );
}
