import { apiFileUrl } from "../lib/api.js";
import { getMessages } from "../i18n/translations.js";

/** Render one instance row and prevent duplicate lifecycle requests. */
function InstanceCard({ instance, language, isAdmin, onSelect, onToggleServer }) {
  const { common, status, instances } = getMessages(language);
  const isRunning = instance.status === "running";
  const isChangingState = instance.status === "starting" || instance.status === "stopping";
  const statusLabel = status[instance.status] ?? status.stopped;
  return <article className="instance-row">
    <button className="instance-summary" type="button" onClick={() => onSelect(instance.id)}>
      <span className={`server-icon ${instance.status}`}>{instance.server_icon_updated_at ? <img src={`${apiFileUrl(`/instances/${instance.id}/server-icon`)}&v=${encodeURIComponent(instance.server_icon_updated_at)}`} alt="" /> : "◆"}</span>
      <span><strong>{instance.name}</strong><small>{instance.jar_filename ?? instances.noJar}</small></span>
      <span className={`status ${instance.status}`}>{statusLabel}</span>
      <span className="chevron">›</span>
    </button>
    <button className={isRunning ? "stop-button" : "start-button"} type="button" title={!isAdmin && instance.start_restricted && !isRunning ? (language === "en" ? "Starts are restricted at this time" : "현재는 서버 시작 제한 시간입니다") : undefined} disabled={isChangingState || (!isAdmin && instance.start_restricted && !isRunning)} onClick={() => onToggleServer(instance.id)}>{isChangingState ? statusLabel : isRunning ? common.stop : !isAdmin && instance.start_restricted ? (language === "en" ? "Restricted" : "이용 제한 시간") : common.start}</button>
  </article>;
}

export default InstanceCard;
