import { useEffect, useState } from "react";
import axios from "axios";
import { Shield, Users, Path, Warning } from "@phosphor-icons/react";
import { Skeleton } from "@/components/ui/skeleton";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BUCKET_COLOR = {
  "battle-tested": "text-[#DFFF00]",
  "well-run": "text-[#DFFF00]",
  "some traffic": "text-amber-400",
  "quiet route": "text-white/60",
  unrun: "text-white/40",
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

  if (!stravaConnected) return null;
  if (!route) return null;

  return (
    <div
      data-testid="strava-safety"
      className="border border-[#FC5200]/40 bg-black rounded-sm overflow-hidden"
    >
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/10 bg-[#FC5200]/10">
        <Shield size={14} className="text-[#FC5200]" weight="fill" />
        <span className="font-mono text-[10px] tracking-[0.25em] text-white/70">
          STRAVA · SAFE & TESTED
        </span>
      </div>
      <div className="p-3 space-y-3">
        {loading && (
          <>
            <Skeleton className="h-4 w-32 bg-white/10" />
            <Skeleton className="h-3 w-full bg-white/10" />
            <Skeleton className="h-3 w-3/4 bg-white/10" />
          </>
        )}
        {error && (
          <div className="text-[11px] text-[#FF3B30] flex items-start gap-1.5">
            <Warning size={12} className="mt-0.5" /> {error}
          </div>
        )}
        {data && !loading && (
          <>
            <div className="flex items-baseline gap-3">
              <div className="font-head text-4xl leading-none text-[#DFFF00]">{data.score}</div>
              <div>
                <div className={`font-head text-sm ${BUCKET_COLOR[data.score_bucket]}`}>
                  {data.score_bucket?.toUpperCase()}
                </div>
                <div className="font-mono text-[9px] text-white/40">
                  {data.total_athletes.toLocaleString()} athletes · {data.overlapping_count} matching segments
                </div>
              </div>
            </div>
            {data.segments?.length > 0 && (
              <ul className="space-y-1.5 pt-2 border-t border-white/10">
                {data.segments.slice(0, 5).map((s) => (
                  <li key={s.id} className="flex items-center gap-2 text-[11px]">
                    <Path size={11} className="text-[#FC5200] shrink-0" />
                    <a
                      href={`https://www.strava.com/segments/${s.id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex-1 truncate text-white/85 hover:text-[#DFFF00] transition-colors"
                      title={s.name}
                    >
                      {s.name}
                    </a>
                    <span className="font-mono text-[10px] text-white/40 flex items-center gap-0.5">
                      <Users size={10} /> {s.athlete_count.toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {data.overlapping_count === 0 && (
              <div className="text-[11px] text-white/50 italic">
                No popular Strava segments overlap this loop — you're pioneering.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
