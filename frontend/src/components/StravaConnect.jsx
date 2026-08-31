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
      if (data.connected && onConnected) onConnected(data);
    } catch {
      setStatus({ connected: false });
    }
  };

  useEffect(() => {
    refresh();
    // Post-callback URL param
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
        className="flex items-center gap-2 border border-white/10 bg-white/5 rounded-sm px-3 py-2"
      >
        {a.profile ? (
          <img src={a.profile} alt="" className="w-7 h-7 rounded-full border border-white/20" />
        ) : (
          <PersonSimpleRun size={20} className="text-[#FC5200]" weight="fill" />
        )}
        <div className="flex-1 min-w-0">
          <div className="font-mono text-[9px] tracking-widest text-white/40">STRAVA</div>
          <div className="text-xs text-white truncate">
            {a.firstname} {a.lastname}
          </div>
        </div>
        <button
          data-testid="strava-disconnect"
          onClick={disconnect}
          className="text-white/40 hover:text-[#FF3B30] transition-colors"
          title="Disconnect"
        >
          <LinkBreak size={14} />
        </button>
      </div>
    );
  }

  return (
    <Button
      data-testid="strava-connect-btn"
      onClick={connect}
      disabled={loading}
      className="w-full h-10 rounded-sm bg-[#FC5200] hover:bg-[#e04a00] text-white font-head text-xs tracking-widest"
    >
      <PersonSimpleRun size={14} weight="fill" className="mr-2" />
      {loading ? "REDIRECTING…" : "CONNECT STRAVA"}
    </Button>
  );
}
