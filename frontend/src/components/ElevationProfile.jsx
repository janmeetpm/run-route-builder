import { PANELS } from "@/constants/testIds";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";

export default function ElevationProfile({ route }) {
  if (!route?.elevations?.length) return null;
  const data = route.elevations.map((e, i) => ({
    km: +(route.cumulative_distance_m[i] / 1000).toFixed(2),
    elev: +e.toFixed(1),
  }));
  // Downsample for perf
  const stride = Math.max(1, Math.floor(data.length / 120));
  const sampled = data.filter((_, i) => i % stride === 0);
  const stats = route.elev_stats || {};

  return (
    <div
      data-testid={PANELS.elevation}
      className="absolute left-6 right-[calc(380px+3rem)] bottom-6 h-[180px]
        bg-black/70 backdrop-blur-xl border border-white/15 rounded-md z-10 overflow-hidden"
    >
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/10">
        <div className="flex items-center gap-3">
          <span className="font-mono text-[10px] tracking-[0.25em] text-white/60">ELEVATION PROFILE</span>
          <span className="font-head text-lg text-[#DFFF00]">↑ {stats.ascent_m || 0}m</span>
          <span className="font-head text-lg text-white/70">↓ {stats.descent_m || 0}m</span>
        </div>
        <span className="font-mono text-[10px] text-white/40">
          min {stats.min_m}m · max {stats.max_m}m
        </span>
      </div>
      <div className="w-full h-[140px] px-2 pb-2">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sampled} margin={{ top: 6, right: 8, left: 8, bottom: 0 }}>
            <defs>
              <linearGradient id="volt" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#DFFF00" stopOpacity={0.7} />
                <stop offset="100%" stopColor="#DFFF00" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="km"
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10, fontFamily: "JetBrains Mono" }}
              tickLine={false}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              unit="km"
            />
            <YAxis
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10, fontFamily: "JetBrains Mono" }}
              tickLine={false}
              axisLine={false}
              width={30}
              domain={["dataMin - 3", "dataMax + 3"]}
            />
            <Tooltip
              contentStyle={{
                background: "#0a0a0a",
                border: "1px solid rgba(255,255,255,0.2)",
                fontFamily: "JetBrains Mono",
                fontSize: 11,
                color: "#fff",
              }}
              labelFormatter={(v) => `${v} km`}
              formatter={(v) => [`${v} m`, "elev"]}
            />
            <Area
              type="monotone"
              dataKey="elev"
              stroke="#DFFF00"
              strokeWidth={2}
              fill="url(#volt)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
