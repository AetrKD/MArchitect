import { apiFileUrl } from "../lib/api.js";
import { getMessages } from "../i18n/translations.js";

/** Render one instance row and prevent duplicate lifecycle requests. */
function InstanceCard({ instance, language, onSelect, onToggleServer }) {
  const { common, status, instances } = getMessages(language);
  const isRunning = instance.status === "running";
  const isChangingState = instance.status === "starting" || instance.status === "stopping";
  const statusLabel = status[instance.status] ?? status.stopped;
  return <article className="instance-row">
    <button className="instance-summary" type="button" onClick={() => onSelect(instance.id)}>
      <span className={`server-icon ${instance.status}`}>{instance.server_icon_updated_at ? <img src={`${apiFileUrl(`/instances/${instance.id}/server-icon`)}?v=${encodeURIComponent(instance.server_icon_updated_at)}`} alt="" /> : "◆"}</span>
      <span><strong>{instance.name}</strong><small>{instance.jar_filename ?? instances.noJar}</small></span>
      <span className={`status ${instance.status}`}>{statusLabel}</span>
      <span className="chevron">›</span>
    </button>
    <button className={isRunning ? "stop-button" : "start-button"} type="button" disabled={isChangingState} onClick={() => onToggleServer(instance.id)}>{isChangingState ? statusLabel : isRunning ? common.stop : common.start}</button>
  </article>;
}

export default InstanceCard;
