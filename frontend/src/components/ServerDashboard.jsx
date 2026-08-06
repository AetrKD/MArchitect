import { useEffect, useState } from "react";
import api from "../lib/api.js";
import { getMessages } from "../i18n/translations.js";

/** Format byte values for dashboard labels. */
function formatBytes(value) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(1)} GB`;
}

/** Render a small SVG graph without a chart dependency. */
function MetricChart({ title, value, subtitle, values, secondaryValues = [], maxValue, color = "blue" }) {
  const ceiling = Math.max(maxValue ?? 0, ...values, ...secondaryValues, 1);
  const pointList = (items) => items.map((item, index) => `${index * (320 / Math.max(items.length - 1, 1))},${108 - (item / ceiling) * 92}`).join(" ");
  return <article className={`metric-card ${color}`}>
    <div className="metric-card-heading"><span>{title}</span><strong>{value}</strong></div>
    <small>{subtitle}</small>
    <svg viewBox="0 0 320 120" role="img" aria-label={`${title} 최근 사용량 그래프`}>
      <path className="metric-grid" d="M0 16H320M0 62H320M0 108H320" />
      <polyline points={pointList(values)} />
      {secondaryValues.length > 0 && <polyline className="secondary" points={pointList(secondaryValues)} />}
    </svg>
  </article>;
}

/** Poll system metrics and display the latest ten samples. */
function ServerDashboard({ instances, language }) {
  const [metrics, setMetrics] = useState(null);
  const [history, setHistory] = useState({ disk: [], download: [], upload: [] });
  const { dashboard: text, status } = getMessages(language);

  useEffect(() => {
    let isActive = true;
    async function loadMetrics() {
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
        // Keep the last successful graph when a sample fails temporarily.
      }
    }
    loadMetrics();
    const intervalId = window.setInterval(loadMetrics, 2000);
    return () => { isActive = false; window.clearInterval(intervalId); };
  }, []);

  if (!metrics) return <section className="dashboard-metrics"><h2>{text.dashboard}</h2><p className="empty-message">{text.loading}</p></section>;
  const diskPercent = metrics.disk_total ? (metrics.disk_used / metrics.disk_total) * 100 : 0;
  return <section className="dashboard-metrics">
    <div className="section-title"><div><h2>{text.dashboard}</h2><span>{text.interval}</span></div></div>
    <div className="metric-grid-layout">
      <MetricChart title={text.disk} value={`${formatBytes(metrics.disk_used)} / ${formatBytes(metrics.disk_total)}`} subtitle={`${text.storage} · ${diskPercent.toFixed(1)}%`} values={history.disk} maxValue={metrics.disk_total} color="orange" />
      <MetricChart title={text.traffic} value={`↓ ${formatBytes(metrics.network_download_bps)}/s · ↑ ${formatBytes(metrics.network_upload_bps)}/s`} subtitle={text.trafficHelp} values={history.download} secondaryValues={history.upload} color="green" />
    </div>
    <section className="instance-resource-section">
      <h2>{text.resources}</h2>
      <div className="instance-resource-list">{instances.map((instance) => {
        const resource = instance.resource_metrics;
        return <article className="instance-resource-card" key={instance.id}>
          <strong>{instance.name}</strong>
          {resource ? <div className="instance-resource-values"><span>CPU <b>{resource.cpu_percent}%</b></span><span>{text.memory}<b>{formatBytes(resource.memory_used)}</b></span></div> : <span className="status stopped">{status.stopped}</span>}
        </article>;
      })}</div>
    </section>
  </section>;
}

export default ServerDashboard;
