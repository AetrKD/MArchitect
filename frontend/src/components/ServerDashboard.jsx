import { useEffect, useState } from "react";
import api from "../lib/api.js";

function formatBytes(value) {
  // 바이트 값을 화면에 읽기 쉬운 크기 단위로 변환합니다.
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(1)} GB`;
}

function MetricChart({ title, value, subtitle, values, secondaryValues = [], maxValue, color = "blue" }) {
  // Render a lightweight SVG history graph without an additional chart library.
  const ceiling = Math.max(maxValue ?? 0, ...values, ...secondaryValues, 1);
  const points = values.map((item, index) => `${index * (320 / Math.max(values.length - 1, 1))},${108 - (item / ceiling) * 92}`).join(" ");
  const secondaryPoints = secondaryValues.map((item, index) => `${index * (320 / Math.max(secondaryValues.length - 1, 1))},${108 - (item / ceiling) * 92}`).join(" ");
  return <article className={`metric-card ${color}`}><div className="metric-card-heading"><span>{title}</span><strong>{value}</strong></div><small>{subtitle}</small><svg viewBox="0 0 320 120" role="img" aria-label={`${title} 최근 사용량 그래프`}><path className="metric-grid" d="M0 16H320M0 62H320M0 108H320" /><polyline points={points} />{secondaryPoints && <polyline className="secondary" points={secondaryPoints} />}</svg></article>;
}

function ServerDashboard({ instances, language }) {
  // Poll the backend every two seconds and retain only the most recent 10 samples.
  const [metrics, setMetrics] = useState(null);
  const [history, setHistory] = useState({ disk: [], download: [], upload: [] });
  const isEnglish = language === "en";
  const text = isEnglish ? {
    dashboard: "Server dashboard", loading: "Loading system metrics...", interval: "Every 2 seconds · container scope", disk: "Disk usage", storage: "Instance storage", traffic: "Network traffic", trafficHelp: "Blue: download · gray: upload", resources: "Instance resources", running: "CPU share of container · live memory", stopped: "The server is not running.", stoppedBadge: "Stopped",
  } : {
    dashboard: "서버 대시보드", loading: "시스템 사용량을 불러오는 중입니다.", interval: "2초 간격 · 컨테이너 기준", disk: "디스크 사용량", storage: "인스턴스 저장소", traffic: "네트워크 트래픽", trafficHelp: "파랑: 다운로드 · 회색: 업로드", resources: "인스턴스 리소스", running: "컨테이너 전체 CPU 대비 · 실시간 메모리", stopped: "서버가 실행 중이 아닙니다.", stoppedBadge: "정지됨",
  };

  useEffect(() => {
    let isActive = true;
    async function loadMetrics() {
      // 한 번의 대시보드 표본을 받고 최근 10개 값만 그래프 이력에 남깁니다.
      try {
        const response = await api.get("/system/metrics");
        if (!isActive) return;
        const sample = response.data;
        setMetrics(sample);
        setHistory((current) => ({
          disk: [...current.disk, sample.disk_used].slice(-10),
          download: [...current.download, sample.network_download_bps].slice(-10),
          upload: [...current.upload, sample.network_upload_bps].slice(-10),
        }));
      } catch {
        // A temporary failed sample should not remove the already shown graph.
      }
    }
    loadMetrics();
    const intervalId = window.setInterval(loadMetrics, 2000);
    return () => { isActive = false; window.clearInterval(intervalId); };
  }, []);

  if (!metrics) return <section className="dashboard-metrics"><h2>{text.dashboard}</h2><p className="empty-message">{text.loading}</p></section>;
  const diskPercent = metrics.disk_total ? (metrics.disk_used / metrics.disk_total) * 100 : 0;
  return <section className="dashboard-metrics"><div className="section-title"><div><h2>{text.dashboard}</h2><span>{text.interval}</span></div></div><div className="metric-grid-layout"><MetricChart title={text.disk} value={`${formatBytes(metrics.disk_used)} / ${formatBytes(metrics.disk_total)}`} subtitle={`${text.storage} · ${diskPercent.toFixed(1)}%`} values={history.disk} maxValue={metrics.disk_total} color="orange" /><MetricChart title={text.traffic} value={`↓ ${formatBytes(metrics.network_download_bps)}/s · ↑ ${formatBytes(metrics.network_upload_bps)}/s`} subtitle={text.trafficHelp} values={history.download} secondaryValues={history.upload} color="green" /></div><section className="instance-resource-section"><h2>{text.resources}</h2><div className="instance-resource-list">{instances.map((instance) => { const resource = instance.resource_metrics; const isActive = Boolean(resource); return <article className="instance-resource-card" key={instance.id}><div><strong>{instance.name}</strong><small>{isActive ? text.running : text.stopped}</small></div>{isActive ? <div className="instance-resource-values"><span>CPU <b>{resource.cpu_percent}%</b></span><span>{isEnglish ? "Memory" : "메모리"}<b>{formatBytes(resource.memory_used)}</b></span></div> : <span className="status stopped">{text.stoppedBadge}</span>}</article>; })}</div></section></section>;
}

export default ServerDashboard;
