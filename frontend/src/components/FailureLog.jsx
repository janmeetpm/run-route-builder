import { PANELS } from "@/constants/testIds";
import { Terminal, WarningOctagon, CheckCircle, Info } from "@phosphor-icons/react";

const LEVEL = {
  info: "text-[color:var(--ink-mute)]",
  success: "text-[color:var(--forest)]",
  warn: "text-[#a86a1a]",
  error: "text-[color:var(--terracotta)]",
};

const ICON = {
  info: Info,
  success: CheckCircle,
  warn: WarningOctagon,
  error: WarningOctagon,
};

export default function FailureLog({ entries, llmGuess }) {
  const hasFail = entries?.some((e) => e.level === "error");
  return (
    <div
      data-testid={PANELS.failureLog}
      className="border border-[color:var(--line-strong)] bg-[color:var(--surface-2)] rounded-lg overflow-hidden"
    >
      <div className="flex items-center gap-2 px-4 py-2.5">
        <Terminal size={13} className={hasFail ? "text-[color:var(--terracotta)]" : "text-[color:var(--forest)]"} />
        <span className="mut-caps text-[9px]">Failure log · LLM vs Map API</span>
      </div>
      <div className="px-4 pb-4 font-mono text-[11px] leading-relaxed space-y-1.5 max-h-[180px] overflow-y-auto no-scrollbar">
        {llmGuess && (
          <div className="text-[color:var(--ink-mute)] border-l border-[color:var(--line-strong)] pl-3 pb-1 mb-1">
            <div className="italic text-[color:var(--ink-soft)]">"{llmGuess.reasoning}"</div>
            <div>
              est {llmGuess.estimated_distance_km} km · err{" "}
              <span
                className={
                  llmGuess.distance_error_pct > 15
                    ? "text-[color:var(--terracotta)]"
                    : "text-[color:var(--forest)]"
                }
              >
                {llmGuess.distance_error_pct}%
              </span>
            </div>
          </div>
        )}
        {(entries || []).map((e, i) => {
          const Icon = ICON[e.level] || Info;
          return (
            <div key={i} className={`flex items-start gap-2 ${LEVEL[e.level] || LEVEL.info}`}>
              <Icon size={11} className="mt-[3px] shrink-0" />
              <div className="flex-1">
                <span className="text-[color:var(--ink-mute)]">[{e.stage}]</span>{" "}
                <span>{e.message}</span>
              </div>
            </div>
          );
        })}
        {!entries?.length && (
          <div className="text-[color:var(--ink-mute)] italic">// build a route to see the log</div>
        )}
      </div>
    </div>
  );
}
