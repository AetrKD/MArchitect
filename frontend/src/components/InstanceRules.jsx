import { useEffect, useState } from "react";
import api from "../lib/api.js";

export default function InstanceRules({ instanceId, language, onNotify }) {
  const en = language === "en";
  const [config, setConfig] = useState({ rules: [] });
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const weekdays = en ? ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] : ["월", "화", "수", "목", "금", "토", "일"];
  const titles = en ? { start: "Scheduled start", stop: "Scheduled stop", restriction: "Start restriction" } : { start: "예약 시작", stop: "예약 정지", restriction: "이용 제한 시간" };
  useEffect(() => {
    let active = true;
    setLoading(true); setLoaded(false); setError("");
    api.get("/instances/" + instanceId + "/rules").then(({ data }) => { if (active) { setConfig({ rules: data.rules }); setLoaded(true); } })
      .catch(() => { if (active) setError(en ? "Cannot load rules." : "규칙을 불러오지 못했습니다."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [instanceId, en]);
  function update(id, changes) {
    setConfig(current => ({ rules: current.rules.map(rule => rule.id === id ? { ...rule, ...changes } : rule) }));
  }
  function add(kind) {
    const id = Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join("");
    setConfig(current => ({ rules: [...current.rules, { id, kind, enabled: true, days: [0, 1, 2, 3, 4, 5, 6], time: kind === "stop" ? "23:00" : "09:00", end_time: kind === "restriction" ? "18:00" : null }] }));
  }
  async function save(event) {
    event.preventDefault(); setSaving(true); setError("");
    try {
      const { data } = await api.put("/instances/" + instanceId + "/rules", { rules: config.rules });
      setConfig({ rules: data.rules });
      onNotify(en ? "Rules saved." : "규칙을 저장했습니다.");
    } catch (failure) {
      const detail = failure.response?.data?.detail;
      setError(typeof detail === "string" ? detail : en ? "Check weekdays and times. Restriction start and end must differ." : "요일과 시각을 확인하세요. 제한 시작과 종료 시각은 달라야 합니다.");
    } finally { setSaving(false); }
  }
  return <section className="management-section instance-rules"><div className="rules-heading"><h2>{en ? "Instance rules" : "인스턴스 규칙"}</h2><span>{en ? "Uses service timezone" : "서비스 설정 시간대 기준"}</span></div>
    <details className="rules-help"><summary>{en ? "How rules work" : "규칙 사용 안내"}</summary><p>{en ? "Rules run while MArchitect is online; missed times are not replayed. Restrictions block only manual starts by regular users. Administrators and scheduled starts are allowed. Overnight windows use the starting weekday. A scheduled stop wins over a simultaneous start. Change the timezone in Server settings." : "MArchitect가 켜져 있을 때 실행하며 지난 예약은 소급 실행하지 않습니다. 이용 제한은 일반 사용자의 수동 시작만 막으며 관리자와 예약 시작은 허용됩니다. 자정을 넘는 제한은 시작 요일을 선택하세요. 같은 시각에 시작과 정지가 겹치면 정지를 우선합니다. 시간대는 서버 설정에서 변경하세요."}</p></details>
    {error && <p role="alert" className="form-error">{error}</p>}
    {loading ? <p>{en ? "Loading…" : "불러오는 중…"}</p> : loaded ? <form onSubmit={save}><fieldset className="rules-form-fields" disabled={saving}>
      <div className="rules-list">{config.rules.map((rule, index) => <article className={"rule-card" + (rule.enabled ? "" : " rule-disabled")} key={rule.id} aria-label={titles[rule.kind] + " " + (index + 1)}>
        <header className="rule-heading"><strong><span className={"rule-kind rule-kind-" + rule.kind} aria-hidden="true" />{titles[rule.kind]}</strong><label className="rule-enabled"><input type="checkbox" checked={rule.enabled} onChange={event => update(rule.id, { enabled: event.target.checked })} />{rule.enabled ? en ? "Enabled" : "사용" : en ? "Disabled" : "사용 안 함"}</label></header>
        <div className="rule-schedule"><fieldset className="rule-days"><legend>{en ? "Weekdays" : "요일"}</legend><div className="rule-weekdays">{weekdays.map((day, value) => <button key={value} type="button" aria-label={day} aria-pressed={rule.days.includes(value)} className={rule.days.includes(value) ? "selected" : ""} onClick={() => update(rule.id, { days: rule.days.includes(value) ? rule.days.filter(item => item !== value) : [...rule.days, value].sort() })}>{day}</button>)}</div></fieldset>
          <div className="rule-times"><label>{rule.kind === "restriction" ? en ? "From" : "시작" : en ? "Time" : "실행 시각"}<input aria-label={titles[rule.kind] + (en ? " time" : " 시작 시각")} type="time" required value={rule.time} onChange={event => update(rule.id, { time: event.target.value })} /></label>{rule.kind === "restriction" && <><span className="rule-time-separator" aria-hidden="true">–</span><label>{en ? "Until" : "종료"}<input aria-label={en ? "Restriction end time" : "제한 종료 시각"} type="time" required value={rule.end_time || ""} onChange={event => update(rule.id, { end_time: event.target.value })} /></label></>}</div>
        </div>
        <button className="rule-remove" type="button" aria-label={(en ? "Remove " : "규칙 삭제: ") + titles[rule.kind]} title={en ? "Remove rule" : "규칙 삭제"} onClick={() => setConfig(current => ({ rules: current.rules.filter(item => item.id !== rule.id) }))}>×</button>
      </article>)}</div>
      {config.rules.length === 0 && <p className="rules-empty">{en ? "No rules yet. Add a schedule or restriction below." : "등록된 규칙이 없습니다. 예약이나 이용 제한을 추가하세요."}</p>}
      <div className="rule-actions"><div className="rule-add-actions">{["start", "stop", "restriction"].map(kind => <button className="cancel-button" key={kind} type="button" disabled={config.rules.length >= 100} onClick={() => add(kind)}>+ {titles[kind]}</button>)}</div><button className="create-button" type="submit">{saving ? en ? "Saving…" : "저장 중…" : en ? "Save rules" : "규칙 저장"}</button></div>
    </fieldset></form> : <p>{en ? "Reopen this tab to retry." : "다른 탭으로 이동한 뒤 규칙 탭을 다시 열어주세요."}</p>}
  </section>;
}
