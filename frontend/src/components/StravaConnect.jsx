import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { LinkBreak, PersonSimpleRun } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function StravaConnect({ onConnected }) {
  const [status, setStatus] = useState({ connected: false });
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    try {
      const { data } = await axios.get(`${API}/strava/status`, { withCredentials: true });
      setStatus(data);
      if (onConnected) onConnected(data);
    } catch {
      setStatus({ connected: false });
    }
  };

  useEffect(() => {
    refresh();
    const params = new URLSearchParams(window.location.search);
    if (params.get("strava") === "connected") {
      toast.success("Strava connected. Pulling your runs…");
      window.history.replaceState({}, "", "/");
      setTimeout(refresh, 200);
    } else if (params.get("strava") === "error") {
      toast.error("Strava connection failed. Try again.");
      window.history.replaceState({}, "", "/");
    }
    // eslint-disable-next-line
  }, []);

  const connect = () => {
    setLoading(true);
    window.location.href = `${API}/strava/authorize`;
  };

  const disconnect = async () => {
    await axios.post(`${API}/strava/logout`, {}, { withCredentials: true });
    toast.success("Disconnected from Strava.");
    setStatus({ connected: false });
    if (onConnected) onConnected({ connected: false });
  };

  if (status.connected) {
    const a = status.athlete || {};
    return (
      <div
        data-testid="strava-connected"
        className="flex items-center gap-3 border border-[color:var(--line)] bg-white rounded-md px-3 py-2"
      >
        {a.profile ? (
          <img src={a.profile} alt="" className="w-7 h-7 rounded-full border border-[color:var(--line-strong)]" />
        ) : (
          <PersonSimpleRun size={18} className="text-[color:var(--strava)]" weight="fill" />
        )}
        <div className="flex-1 min-w-0">
          <div className="mut-caps text-[8px]">Strava</div>
          <div className="text-[12px] text-[color:var(--ink)] truncate">
            {a.firstname} {a.lastname}
          </div>
        </div>
        <button
          data-testid="strava-disconnect"
          onClick={disconnect}
          className="text-[color:var(--ink-mute)] hover:text-[color:var(--terracotta)] transition-colors"
          title="Disconnect"
        >
          <LinkBreak size={13} />
        </button>
      </div>
    );
  }

  return (
    <Button
      data-testid="strava-connect-btn"
      onClick={connect}
      disabled={loading}
      variant="outline"
      className="w-full h-10 rounded-md border-[color:var(--strava-40)] bg-transparent hover:bg-[color:var(--strava-08)] text-[color:var(--strava)] font-head text-xs"
    >
      <PersonSimpleRun size={14} weight="fill" className="mr-2" />
      {loading ? "Redirecting…" : "Connect Strava"}
    </Button>
  );
}
