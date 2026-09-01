import { PANELS } from "@/constants/testIds";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";

export default function ElevationProfile({ route }) {
  if (!route?.elevations?.length) return null;
  const data = route.elevations.map((e, i) => ({
    km: +(route.cumulative_distance_m[i] / 1000).toFixed(2),
    elev: +e.toFixed(1),
  }));
  const stride = Math.max(1, Math.floor(data.length / 120));
  const sampled = data.filter((_, i) => i % stride === 0);
  const stats = route.elev_stats || {};

  return (
    <div
      data-testid={PANELS.elevation}
      className="absolute left-6 right-[calc(380px+3rem)] bottom-6 h-[170px]
        bg-white/95 backdrop-blur-sm border border-[color:var(--line-strong)] rounded-lg z-10 overflow-hidden
        shadow-[0_10px_30px_-15px_rgba(26,34,28,0.2)]"
    >
      <div className="flex items-center justify-between px-4 py-2.5">
        <div className="flex items-baseline gap-4">
          <span className="mut-caps text-[9px]">Elevation</span>
          <span className="font-display text-lg text-[color:var(--forest)]">↑ {stats.ascent_m || 0}m</span>
          <span className="font-display text-lg text-[color:var(--ink-mute)]">↓ {stats.descent_m || 0}m</span>
        </div>
        <span className="font-mono text-[10px] text-[color:var(--ink-mute)]">
          min {stats.min_m}m · max {stats.max_m}m
        </span>
      </div>
      <div className="w-full h-[125px] px-2 pb-2">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={sampled} margin={{ top: 4, right: 8, left: 4, bottom: 0 }}>
            <defs>
              <linearGradient id="forest" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2F5D3F" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#2F5D3F" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="km"
              tick={{ fill: "rgba(26,34,28,0.45)", fontSize: 10, fontFamily: "JetBrains Mono" }}
              tickLine={false}
              axisLine={{ stroke: "rgba(26,34,28,0.1)" }}
              unit="km"
              interval="preserveStartEnd"
              minTickGap={90}
            />
            <YAxis
              tick={{ fill: "rgba(26,34,28,0.45)", fontSize: 10, fontFamily: "JetBrains Mono" }}
              tickLine={false}
              axisLine={false}
              width={30}
              domain={["dataMin - 3", "dataMax + 3"]}
            />
            <Tooltip
              contentStyle={{
                background: "#fff",
                border: "1px solid rgba(26,34,28,0.15)",
                fontFamily: "JetBrains Mono",
                fontSize: 11,
                color: "#1a221c",
                borderRadius: 6,
              }}
              labelFormatter={(v) => `${v} km`}
              formatter={(v) => [`${v} m`, "elev"]}
            />
            <Area
              type="monotone"
              dataKey="elev"
              stroke="#2F5D3F"
              strokeWidth={2}
              fill="url(#forest)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
