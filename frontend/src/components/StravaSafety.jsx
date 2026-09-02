import { useEffect, useState } from "react";
import axios from "axios";
import { Shield, Users, Path, Warning } from "@phosphor-icons/react";
import { Skeleton } from "@/components/ui/skeleton";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BUCKET_COLOR = {
  "battle-tested": "text-[color:var(--forest)]",
  "well-run": "text-[color:var(--forest)]",
  "some traffic": "text-[#c8892e]",
  "quiet route": "text-[color:var(--ink-mute)]",
  unrun: "text-[color:var(--ink-mute)]",
};

export default function StravaSafety({ route, stravaConnected }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!route?.coordinates?.length || !stravaConnected) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    axios
      .post(
        `${API}/routes/rank_by_strava`,
        { coordinates: route.coordinates, activity_type: "running" },
        { withCredentials: true, timeout: 30000 }
      )
      .then(({ data }) => setData(data))
      .catch((e) => setError(e.response?.data?.detail || "Strava lookup failed"))
      .finally(() => setLoading(false));
  }, [route?.id, stravaConnected]);

  if (!stravaConnected || !route) return null;

  return (
    <div
      data-testid="strava-safety"
      className="border border-[color:var(--line-strong)] bg-[color:var(--surface-2)] rounded-lg overflow-hidden"
    >
      <div className="flex items-center gap-2 px-4 py-2.5">
        <Shield size={13} className="text-[color:var(--forest)]" weight="fill" />
        <span className="mut-caps text-[9px]">Safe & tested · Strava</span>
      </div>
      <div className="px-4 pb-4 space-y-3">
        {loading && <><Skeleton className="h-4 w-32" /><Skeleton className="h-3 w-full" /></>}
        {error && (
          <div className="text-[11px] text-[color:var(--terracotta)] flex items-start gap-1.5">
            <Warning size={12} className="mt-0.5" /> {error}
          </div>
        )}
        {data && !loading && !error && !data.error && typeof data.score === "number" && (
          <>
            <div className="flex items-baseline gap-3">
              <div className="font-display text-[42px] leading-none text-[color:var(--forest)]">{data.score}</div>
              <div>
                <div className={`font-head text-[13px] ${BUCKET_COLOR[data.score_bucket]} capitalize`}>
                  {data.score_bucket}
                </div>
                <div className="font-mono text-[9px] text-[color:var(--ink-mute)]">
                  {(data.total_athletes || 0).toLocaleString()} athletes · {data.overlapping_count || 0} segments
                </div>
              </div>
            </div>
            {data.segments?.length > 0 && (
              <ul className="space-y-1.5 pt-2 border-t border-[color:var(--line)]">
                {data.segments.slice(0, 5).map((s) => (
                  <li key={s.id} className="flex items-center gap-2 text-[12px]">
                    <Path size={11} className="text-[color:var(--forest)] shrink-0" />
                    <a
                      href={`https://www.strava.com/segments/${s.id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex-1 truncate text-[color:var(--ink-soft)] hover:text-[color:var(--forest)] transition-colors"
                      title={s.name}
                    >
                      {s.name}
                    </a>
                    <span className="font-mono text-[10px] text-[color:var(--ink-mute)] flex items-center gap-0.5">
                      <Users size={10} /> {(s.athlete_count || 0).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {(data.overlapping_count || 0) === 0 && (
              <div className="text-[11px] text-[color:var(--ink-mute)] italic">
                No popular Strava segments overlap this loop — you're pioneering.
              </div>
            )}
          </>
        )}
        {data && !loading && !error && data.error && (
          <div className="text-[11px] text-[color:var(--ink-mute)] italic">
            Strava segment lookup unavailable{data.error === "rate_limited" ? " (rate-limited)" : ""} — try again shortly.
          </div>
        )}
      </div>
    </div>
  );
}
