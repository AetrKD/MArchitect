import { apiFileUrl } from "../lib/api.js";

function InstanceCard({ instance, onSelect, onToggleServer }) {
  // 목록에서 인스턴스 상태, 상세 이동과 관리자 작업을 표시합니다.
  const isRunning = instance.status === "running";

  return (
    <article className="instance-row">
      <button className="instance-summary" type="button" onClick={() => onSelect(instance.id)}>
        <span className={`server-icon ${instance.status}`}>{instance.server_icon_updated_at ? <img src={`${apiFileUrl(`/instances/${instance.id}/server-icon`)}?v=${encodeURIComponent(instance.server_icon_updated_at)}`} alt="" /> : "◆"}</span>
        <span>
          <strong>{instance.name}</strong>
          <small>{instance.jar_filename ?? "JAR 파일 정보 없음"}</small>
        </span>
        <span className={`status ${instance.status}`}>{isRunning ? "실행 중" : "정지됨"}</span>
        <span className="chevron">›</span>
      </button>
      <button className={isRunning ? "stop-button" : "start-button"} type="button" onClick={() => onToggleServer(instance.id)}>{isRunning ? "정지" : "시작"}</button>
    </article>
  );
}

export default InstanceCard;
