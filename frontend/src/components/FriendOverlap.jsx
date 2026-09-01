import { useEffect, useState } from "react";
import axios from "axios";
import { Users, Clock, ArrowSquareOut } from "@phosphor-icons/react";
import { Skeleton } from "@/components/ui/skeleton";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function FriendOverlap({ route, stravaConnected }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!route?.coordinates?.length || !stravaConnected) {
      setData(null);
      return;
    }
    setLoading(true);
    axios
      .post(
        `${API}/routes/friend_overlap`,
        { coordinates: route.coordinates, activity_type: "running" },
        { withCredentials: true, timeout: 20000 }
      )
      .then(({ data }) => setData(data))
      .catch(() => setData({ matches: [], checked: 0 }))
      .finally(() => setLoading(false));
  }, [route?.id, stravaConnected]);

  if (!stravaConnected || !route) return null;

  return (
    <div
      data-testid="friend-overlap"
      className="border border-[color:var(--line-strong)] bg-[color:var(--surface-2)] rounded-lg overflow-hidden"
    >
      <div className="flex items-center gap-2 px-4 py-2.5">
        <Users size={13} className="text-[color:var(--strava)]" />
        <span className="mut-caps text-[9px]">You've been here before</span>
      </div>
      <div className="px-4 pb-4 space-y-2">
        {loading && <><Skeleton className="h-4 w-32" /><Skeleton className="h-3 w-full" /></>}
        {data && !loading && data.matches?.length > 0 && (
          <>
            <div className="text-[12px] text-[color:var(--ink-soft)]">
              You have run <b>{data.matches.length}</b> similar loop{data.matches.length > 1 ? "s" : ""} recently:
            </div>
            <ul className="space-y-1.5">
              {data.matches.slice(0, 4).map((m) => (
                <li key={m.id} className="flex items-center gap-2 text-[12px]">
                  <Clock size={11} className="text-[color:var(--ink-mute)] shrink-0" />
                  <a
                    href={`https://www.strava.com/activities/${m.id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-1 truncate text-[color:var(--ink-soft)] hover:text-[color:var(--forest)]"
                  >
                    {m.name}
                  </a>
                  <span className="font-mono text-[10px] text-[color:var(--ink-mute)]">
                    {fmtDate(m.start_date_local)}
                  </span>
                  <ArrowSquareOut size={10} className="text-[color:var(--ink-mute)]" />
                </li>
              ))}
            </ul>
          </>
        )}
        {data && !loading && data.matches?.length === 0 && (
          <div className="text-[12px] text-[color:var(--ink-mute)] italic">
            A first for you. Checked your last {data.checked || 0} runs — no overlap yet.
          </div>
        )}
      </div>
    </div>
  );
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const days = Math.floor((Date.now() - d.getTime()) / (1000 * 60 * 60 * 24));
  if (days === 0) return "today";
  if (days === 1) return "1d ago";
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return d.toLocaleDateString();
}
