import { useState } from "react";
import axios from "axios";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Envelope, ArrowRight, CalendarBlank, Path, Users } from "@phosphor-icons/react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function WeeklyDigest({ city, distanceKm = 5 }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await axios.get(`${API}/digest/preview`, {
        params: { city, distance_km: distanceKm },
      });
      setData(data);
    } catch {
      toast.error("Could not build digest.");
    } finally {
      setLoading(false);
    }
  };

  const subscribe = async () => {
    if (!email.match(/^[^@]+@[^@]+\.[^@]+$/)) {
      toast.error("Enter a valid email");
      return;
    }
    try {
      await axios.post(`${API}/digest/subscribe`, {
        email, city, distance_km: distanceKm,
      });
      toast.success("Subscribed. Sunday-morning previews are live in-app for now.");
      setEmail("");
    } catch {
      toast.error("Could not subscribe.");
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { setOpen(v); if (v && !data) load(); }}>
      <DialogTrigger asChild>
        <Button
          data-testid="weekly-digest-btn"
          variant="outline"
          className="w-full rounded-md border-[color:var(--line-strong)] bg-transparent hover:bg-[color:var(--surface-2)] text-[color:var(--ink)] font-head text-xs h-9"
        >
          <Envelope size={13} className="mr-2 text-[color:var(--forest)]" />
          Sunday digest preview
        </Button>
      </DialogTrigger>
      <DialogContent
        data-testid="weekly-digest-dialog"
        className="max-w-2xl bg-[color:var(--surface-2)] border-[color:var(--line-strong)] text-[color:var(--ink)] p-0 overflow-hidden"
      >
        <div className="bg-[color:var(--forest)] text-white px-8 py-6">
          <div className="mut-caps text-white/70 mb-1">Trailscribe · Sunday digest</div>
          <DialogHeader>
            <DialogTitle className="font-display text-3xl text-white leading-tight capitalize">
              Your week in {city}
            </DialogTitle>
            <DialogDescription className="sr-only">
              Sunday preview of curated running routes for {city}.
            </DialogDescription>
          </DialogHeader>
          {data && (
            <div className="mt-2 font-mono text-[11px] text-white/70">
              Week of {data.week_of} · targeting {data.target_distance_km} km
            </div>
          )}
        </div>

        <div className="px-8 py-6 max-h-[60vh] overflow-y-auto space-y-4">
          {loading && <div className="text-[color:var(--ink-mute)]">Building your digest…</div>}
          {data?.picks?.map((p, i) => (
            <div
              key={p.id}
              className="flex gap-4 items-start border-b border-[color:var(--line)] pb-4 last:border-0 last:pb-0"
            >
              <div className="font-display text-2xl text-[color:var(--forest)] leading-none w-8 shrink-0">
                {String(i + 1).padStart(2, "0")}
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-head text-[16px] text-[color:var(--ink)]">{p.name}</div>
                <div className="text-[13px] text-[color:var(--ink-soft)] mt-1 leading-relaxed">{p.blurb}</div>
                <div className="flex gap-4 mt-2 font-mono text-[10px] text-[color:var(--ink-mute)]">
                  <span className="flex items-center gap-1"><Path size={10} />{p.distance_km} km</span>
                  <span className="flex items-center gap-1"><CalendarBlank size={10} />{p.difficulty}</span>
                  <span className="flex items-center gap-1"><Users size={10} />{p.athletes_this_week}/wk</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="border-t border-[color:var(--line)] bg-white px-8 py-4">
          <div className="mut-caps mb-2">Want it every Sunday?</div>
          <div className="flex gap-2">
            <input
              data-testid="digest-email-input"
              type="email"
              placeholder="you@run.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="flex-1 bg-white border border-[color:var(--line-strong)] rounded-md px-3 py-2 text-sm text-[color:var(--ink)]"
            />
            <Button
              data-testid="digest-subscribe-btn"
              onClick={subscribe}
              className="rounded-md bg-[color:var(--ink)] hover:bg-[color:var(--forest)] text-white font-head text-xs"
            >
              Notify me <ArrowRight size={12} className="ml-1" />
            </Button>
          </div>
          <div className="mt-2 font-mono text-[9px] text-[color:var(--ink-mute)]">
            Live email delivery is off in this preview — subscription is saved for later.
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
