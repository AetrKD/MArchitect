import { useEffect, useState } from "react";
import api from "../lib/api.js";

export default function TimeSettings({ language, onNotify }) {
  const en = language === "en";
  const [zone, setZone] = useState("system");
  const [custom, setCustom] = useState("Asia/Seoul");
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api.get("/settings/time").then(({ data }) => {
      if (active) { setZone(data.timezone === "system" ? "system" : "custom"); if (data.timezone !== "system") setCustom(data.timezone); setLoaded(true); }
    }).catch(() => { if (active) setError(en ? "Cannot load timezone. Reopen settings to retry." : "시간대를 불러오지 못했습니다. 설정 화면을 다시 열어주세요."); });
    return () => { active = false; };
  }, [en]);
  async function save(event) {
    event.preventDefault(); setSaving(true); setError("");
    try {
      await api.put("/settings/time", { timezone: zone === "system" ? "system" : custom.trim() });
      window.dispatchEvent(new Event("marchitect-clock-updated"));
      onNotify(en ? "Timezone saved." : "시간대를 저장했습니다.");
    } catch (failure) {
      const detail = failure.response?.data?.detail;
      setError(typeof detail === "string" ? detail : en ? "Enter a valid IANA timezone, e.g. Asia/Seoul." : "유효한 IANA 시간대를 입력하세요. 예: Asia/Seoul");
    } finally { setSaving(false); }
  }
  return <section className="management-section"><h2>{en ? "Date and time" : "날짜 및 시간"}</h2><p>{en ? "The service clock and instance rules using the service default follow this timezone. The clock uses server time." : "서비스 시계와 기본 시간대를 사용하는 인스턴스 규칙에 적용합니다. 현재 시각은 서버 시간을 기준으로 표시합니다."}</p><form className="instance-form" onSubmit={save}><label htmlFor="service-timezone">{en ? "Timezone" : "시간대"}</label><select id="service-timezone" disabled={!loaded || saving} value={zone} onChange={event => setZone(event.target.value)}><option value="system">{en ? "Use server system timezone" : "서버 시스템 시간대 사용"}</option><option value="custom">{en ? "Specify timezone" : "시간대 직접 지정"}</option></select>{zone === "custom" && <><label htmlFor="service-timezone-custom">{en ? "IANA timezone" : "IANA 시간대"}</label><input id="service-timezone-custom" list="common-timezones" value={custom} maxLength={100} required disabled={!loaded || saving} onChange={event => setCustom(event.target.value)} placeholder="Asia/Seoul" /><datalist id="common-timezones">{["Asia/Seoul", "Asia/Tokyo", "UTC", "America/New_York", "America/Los_Angeles", "Europe/London"].map(value => <option key={value} value={value} />)}</datalist></>}{error && <p className="form-error" role="alert">{error}</p>}<button className="create-button" type="submit" disabled={!loaded || saving}>{saving ? en ? "Saving…" : "저장 중…" : en ? "Save timezone" : "시간대 저장"}</button></form></section>;
}
