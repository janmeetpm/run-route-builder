import { Thermometer, Wind, Sun, MoonStars, Drop, CloudRain } from "@phosphor-icons/react";

const AQI_COLOR = {
  good: "text-[#DFFF00]",
  fair: "text-[#DFFF00]",
  moderate: "text-amber-400",
  poor: "text-orange-400",
  "very poor": "text-[#FF3B30]",
  "extremely poor": "text-[#FF3B30]",
  unknown: "text-white/40",
};

export default function WeatherStrip({ weather }) {
  if (!weather) return null;
  const {
    temperature_c, feels_like_c, wind_kmh, precip_prob_pct,
    aqi, aqi_bucket, sunrise, before_sunrise, uv_index_max,
  } = weather;

  const srTime = sunrise ? sunrise.split("T")[1]?.slice(0, 5) : "—";
  const sunriseLabel = sunrise
    ? (before_sunrise ? "PRE-DAWN" : "DAYLIGHT")
    : "UNAVAILABLE";
  const SunriseIcon = sunrise ? (before_sunrise ? MoonStars : Sun) : MoonStars;

  return (
    <div
      data-testid="weather-strip"
      className="absolute bottom-[210px] left-6 flex items-stretch gap-2 z-10"
    >
      <Chip icon={<Thermometer size={13} />} label="TEMP" value={temperature_c != null ? `${temperature_c}°` : "—"}
            sub={feels_like_c != null ? `feels ${feels_like_c}°` : null} />
      <Chip
        icon={<Wind size={13} />}
        label="AIR"
        value={aqi != null ? aqi : "—"}
        sub={aqi_bucket?.toUpperCase()}
        valueClass={AQI_COLOR[aqi_bucket] || "text-white"}
      />
      <Chip icon={<SunriseIcon size={13} />}
            label="SUNRISE" value={srTime}
            sub={sunriseLabel} />
      <Chip icon={<CloudRain size={13} />} label="RAIN"
            value={precip_prob_pct != null ? `${precip_prob_pct}%` : "—"}
            sub={wind_kmh != null ? `${wind_kmh} km/h wind` : null} />
      {uv_index_max != null && (
        <Chip icon={<Sun size={13} />} label="UV MAX" value={uv_index_max} sub={uvBucket(uv_index_max)} />
      )}
    </div>
  );
}

function Chip({ icon, label, value, sub, valueClass = "text-white" }) {
  return (
    <div className="bg-black/70 backdrop-blur-xl border border-white/15 rounded-sm px-3 py-1.5 min-w-[92px]">
      <div className="flex items-center gap-1 text-white/40">
        {icon}
        <span className="font-mono text-[9px] tracking-[0.25em]">{label}</span>
      </div>
      <div className={`font-head text-base leading-none mt-0.5 ${valueClass}`}>{value}</div>
      {sub && <div className="font-mono text-[9px] text-white/40 mt-0.5">{sub}</div>}
    </div>
  );
}

function uvBucket(v) {
  if (v < 3) return "LOW";
  if (v < 6) return "MODERATE";
  if (v < 8) return "HIGH";
  if (v < 11) return "VERY HIGH";
  return "EXTREME";
}
