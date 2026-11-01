import { useEffect, useState } from "react";
import api from "../lib/api.js";

export default function ServiceClock({ language }) {
  const [sample, setSample] = useState(null);
  const [tick, setTick] = useState(performance.now());
  const [stale, setStale] = useState(false);
  const en = language === "en";
  useEffect(() => {
    let active = true;
    let pending = false;
    async function sync() {
      if (pending) return;
      pending = true;
      try {
        const { data } = await api.get("/settings/time");
        if (active) { setSample({ ...data, received: performance.now() }); setStale(false); }
      } catch { if (active) setStale(true); }
      finally { pending = false; }
    }
    sync();
    const refresh = window.setInterval(sync, 30000);
    const seconds = window.setInterval(() => setTick(performance.now()), 1000);
    window.addEventListener("marchitect-clock-updated", sync);
    return () => { active = false; clearInterval(refresh); clearInterval(seconds); window.removeEventListener("marchitect-clock-updated", sync); };
  }, []);
  const epoch = sample ? Date.parse(sample.current_time) + Math.max(0, tick - sample.received) : null;
  const display = sample ? new Date(epoch + sample.utc_offset_seconds * 1000).toLocaleString(en ? "en-GB" : "ko-KR", { timeZone: "UTC", year: "numeric", month: "2-digit", day: "2-digit", weekday: "short", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) : "—";
  return <div className="service-clock"><span>{en ? "Server time" : "서버 시간"}</span><time dateTime={epoch ? new Date(epoch).toISOString() : undefined}>{display}</time><small>{sample ? (sample.timezone === "system" ? (en ? "System · " : "시스템 · ") + sample.timezone_label : sample.timezone) : ""}{stale ? (en ? " · Sync failed" : " · 시간 동기화 실패") : ""}</small></div>;
}
