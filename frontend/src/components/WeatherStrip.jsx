import { Thermometer, Wind, Sun, MoonStars, CloudRain } from "@phosphor-icons/react";

const AQI_COLOR = {
  good: "text-[color:var(--forest)]",
  fair: "text-[color:var(--forest)]",
  moderate: "text-[#c8892e]",
  poor: "text-[#b3543d]",
  "very poor": "text-[color:var(--terracotta)]",
  "extremely poor": "text-[color:var(--terracotta)]",
  unknown: "text-[color:var(--ink-mute)]",
};

export default function WeatherStrip({ weather }) {
  if (!weather) return null;
  const {
    temperature_c, feels_like_c, wind_kmh, precip_prob_pct,
    aqi, aqi_bucket, sunrise, before_sunrise, uv_index_max,
  } = weather;

  const srTime = sunrise ? sunrise.split("T")[1]?.slice(0, 5) : "—";
  const sunriseLabel = sunrise ? (before_sunrise ? "pre-dawn" : "daylight") : "unavailable";
  const SunriseIcon = sunrise ? (before_sunrise ? MoonStars : Sun) : MoonStars;

  return (
    <div
      data-testid="weather-strip"
      className="absolute top-6 right-[calc(380px+3rem)] flex items-stretch gap-1.5 z-10"
    >
      <Chip icon={<Thermometer size={12} />} label="Temp" value={temperature_c != null ? `${temperature_c}°` : "—"}
            sub={feels_like_c != null ? `feels ${feels_like_c}°` : null} />
      <Chip icon={<Wind size={12} />} label="Air" value={aqi != null ? aqi : "—"}
            sub={aqi_bucket} valueClass={AQI_COLOR[aqi_bucket] || ""} />
      <Chip icon={<SunriseIcon size={12} />} label="Sunrise" value={srTime} sub={sunriseLabel} />
      <Chip icon={<CloudRain size={12} />} label="Rain"
            value={precip_prob_pct != null ? `${precip_prob_pct}%` : "—"}
            sub={wind_kmh != null ? `${wind_kmh} km/h wind` : null} />
      {uv_index_max != null && (
        <Chip icon={<Sun size={12} />} label="UV" value={uv_index_max} sub={uvBucket(uv_index_max)} />
      )}
    </div>
  );
}

function Chip({ icon, label, value, sub, valueClass = "text-[color:var(--ink)]" }) {
  return (
    <div className="bg-white/95 backdrop-blur-sm border border-[color:var(--line)] rounded-md px-3 py-1.5 min-w-[80px]">
      <div className="flex items-center gap-1 text-[color:var(--ink-mute)]">
        {icon}
        <span className="mut-caps text-[8px]">{label}</span>
      </div>
      <div className={`font-display text-[16px] leading-none mt-0.5 ${valueClass}`}>{value}</div>
      {sub && <div className="font-mono text-[9px] text-[color:var(--ink-mute)] mt-0.5">{sub}</div>}
    </div>
  );
}

function uvBucket(v) {
  if (v < 3) return "low";
  if (v < 6) return "mod";
  if (v < 8) return "high";
  if (v < 11) return "v.high";
  return "extreme";
}
