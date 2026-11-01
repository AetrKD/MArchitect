import { useEffect, useState } from "react";
import api from "../lib/api.js";

export default function InstanceRules({ instanceId, language, onNotify }) {
  const en = language === "en";
  const [config, setConfig] = useState({ timezone: "Asia/Seoul", rules: [] });
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const weekdays = en ? ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] : ["월", "화", "수", "목", "금", "토", "일"];
  useEffect(() => {
    let active = true;
    setLoading(true); setLoaded(false);
    api.get("/instances/" + instanceId + "/rules").then(({ data }) => { if (active) { setConfig(data); setLoaded(true); } })
      .catch(() => { if (active) setError(en ? "Cannot load rules." : "규칙을 불러오지 못했습니다."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [instanceId, en]);
  function update(id, changes) {
    setConfig(current => ({ ...current, rules: current.rules.map(rule => rule.id === id ? { ...rule, ...changes } : rule) }));
  }
  function add(kind) {
    setConfig(current => ({ ...current, rules: [...current.rules, { id: Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join(""), kind, enabled: true, days: [0, 1, 2, 3, 4, 5, 6], time: kind === "stop" ? "23:00" : "09:00", end_time: kind === "restriction" ? "18:00" : null }] }));
  }
  async function save(event) {
    event.preventDefault();
    setSaving(true); setError("");
    try {
      const { data } = await api.put("/instances/" + instanceId + "/rules", config);
      setConfig(data);
      onNotify(en ? "Rules saved." : "규칙을 저장했습니다.");
    } catch (failure) {
      const detail = failure.response?.data?.detail;
      setError(typeof detail === "string" ? detail : en ? "Check weekdays, times and timezone." : "요일, 시각, 시간대를 확인하세요. 제한 시작과 종료 시각은 달라야 합니다.");
    } finally { setSaving(false); }
  }
  return <section className="management-section instance-rules"><h2>{en ? "Instance rules" : "인스턴스 규칙"}</h2>
    <p>{en ? "Rules run while MArchitect is online. Missed times are not replayed. Restrictions block only manual starts by regular users; administrators and scheduled starts are allowed. Overnight windows belong to the selected starting weekday." : "MArchitect가 켜져 있을 때 예약이 실행되며, 꺼져 있던 동안 지난 예약은 실행하지 않습니다. 이용 제한은 일반 사용자의 수동 시작만 막으며 관리자와 예약 시작은 허용됩니다. 자정을 넘는 제한은 시작하는 요일을 선택하세요."}</p>
    <p>{en ? "Times use the timezone below. A scheduled stop wins if both actions share a time." : "모든 시각은 아래 시간대를 기준으로 합니다. 같은 시각의 예약 시작과 정지가 겹치면 정지를 우선합니다."}</p>
    {error && <p role="alert" className="form-error">{error}</p>}
    {loading ? <p>{en ? "Loading…" : "불러오는 중…"}</p> : loaded ? <form onSubmit={save}><fieldset disabled={saving}>
      <label htmlFor="rules-timezone">{en ? "Timezone" : "시간대"}</label><input id="rules-timezone" value={config.timezone} required onChange={event => setConfig({ ...config, timezone: event.target.value })} placeholder="Asia/Seoul" />
      {config.rules.map((rule, index) => <fieldset className="rule-card" key={rule.id}><legend>{index + 1}. {rule.kind === "start" ? en ? "Scheduled start" : "예약 시작" : rule.kind === "stop" ? en ? "Scheduled stop" : "예약 정지" : en ? "Start restriction" : "이용 제한 시간"}</legend>
        <label><input type="checkbox" checked={rule.enabled} onChange={event => update(rule.id, { enabled: event.target.checked })} /> {en ? "Enabled" : "사용"}</label>
        <div className="rule-weekdays">{weekdays.map((day, value) => <label key={value}><input type="checkbox" checked={rule.days.includes(value)} onChange={event => update(rule.id, { days: event.target.checked ? [...rule.days, value].sort() : rule.days.filter(item => item !== value) })} />{day}</label>)}</div>
        <div className="rule-times"><label>{rule.kind === "restriction" ? en ? "From" : "제한 시작" : en ? "Time" : "실행 시각"}<input type="time" required value={rule.time} onChange={event => update(rule.id, { time: event.target.value })} /></label>
          {rule.kind === "restriction" && <label>{en ? "Until" : "제한 종료"}<input type="time" required value={rule.end_time || ""} onChange={event => update(rule.id, { end_time: event.target.value })} /></label>}</div>
        <button className="delete-button" type="button" onClick={() => setConfig(current => ({ ...current, rules: current.rules.filter(item => item.id !== rule.id) }))}>{en ? "Remove rule" : "규칙 삭제"}</button>
      </fieldset>)}
      <div className="rule-actions">{["start", "stop", "restriction"].map(kind => <button className="cancel-button" key={kind} type="button" disabled={config.rules.length >= 100} onClick={() => add(kind)}>{kind === "start" ? en ? "+ Scheduled start" : "+ 예약 시작" : kind === "stop" ? en ? "+ Scheduled stop" : "+ 예약 정지" : en ? "+ Restriction" : "+ 이용 제한 시간"}</button>)}<button className="create-button" type="submit">{saving ? en ? "Saving…" : "저장 중…" : en ? "Save rules" : "규칙 저장"}</button></div>
    </fieldset></form> : <p>{en ? "Reopen this tab to retry." : "다른 탭으로 이동한 뒤 규칙 탭을 다시 열어주세요."}</p>}
  </section>;
}
