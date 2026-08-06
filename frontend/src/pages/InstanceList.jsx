import InstanceCard from "../components/InstanceCard.jsx";
import ServerDashboard from "../components/ServerDashboard.jsx";
import { getMessages } from "../i18n/translations.js";

/** Format one background task into a concise status label. */
function taskStatus(task, copy) {
  if (task.status === "queued") return copy.queued;
  if (task.status === "running") return task.indeterminate ? "NeoForge 설치 중" : `${copy.inProgress} ${task.progress}%`;
  if (task.status === "completed") return copy.completed;
  return `${copy.failed}: ${task.error}`;
}

/** Render either the system dashboard or the instance list. */
function InstanceList({ instances, isAdmin, language, onCreate, onOpenAdmin, onSelect, onToggleServer, tasks, onDismissTask, onDismissAllTasks, showDashboard = false }) {
  const { dashboard, instances: instanceText, sidebar } = getMessages(language);
  const title = showDashboard ? dashboard.title : instanceText.title;
  const description = showDashboard ? dashboard.description : instanceText.description;
  return <main className="dashboard">
    <header className="page-header">
      <div><p className="eyebrow">MARCHITECT</p><h1>{title}</h1><p>{description}</p></div>
      <div className="header-actions"><span className={`role-badge ${isAdmin ? "admin" : "user"}`}>{isAdmin ? sidebar.admin : sidebar.user}</span>{isAdmin && !showDashboard && <button className="logout-button" type="button" onClick={onOpenAdmin}>{sidebar.java}</button>}</div>
    </header>
    {showDashboard && <ServerDashboard instances={instances} language={language} />}
    {showDashboard && tasks.length > 0 && <section className="management-section task-section">
      <div className="file-browser-heading"><div><h2>{dashboard.backgroundTasks}</h2><p className="section-description">{dashboard.taskHint}</p></div><button className="cancel-button" type="button" onClick={onDismissAllTasks}>{dashboard.acknowledgeAll}</button></div>
      <ul className="runtime-list task-list">{tasks.slice(0, 8).map((task) => <li key={task.id}><button className="task-item" type="button" onClick={() => onDismissTask(task.id)}><strong>{task.title}</strong><span>{taskStatus(task, dashboard)}</span>{task.status === "running" && task.message && <small>{task.message}</small>}{(task.status === "queued" || task.status === "running") && (task.indeterminate ? <progress /> : <progress value={task.progress} max="100" />)}</button></li>)}</ul>
    </section>}
    {!showDashboard && <section className="instances" aria-label="서버 목록"><div className="instance-list">
      {isAdmin && <article className="instance-row create-instance-row"><button className="instance-summary" type="button" onClick={onCreate}><span className="server-icon">+</span><span><strong>{instanceText.createTitle}</strong><small>{instanceText.createDescription}</small></span><span className="status create-status">{instanceText.createBadge}</span><span className="chevron">›</span></button><button className="create-button" type="button" onClick={onCreate}>{instanceText.create}</button></article>}
      {instances.map((instance) => <InstanceCard key={instance.id} instance={instance} language={language} isAdmin={isAdmin} onSelect={onSelect} onToggleServer={onToggleServer} />)}
    </div></section>}
  </main>;
}

export default InstanceList;
