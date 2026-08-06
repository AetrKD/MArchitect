import InstanceCard from "../components/InstanceCard.jsx";
import ServerDashboard from "../components/ServerDashboard.jsx";

function InstanceList({ instances, isAdmin, language, onCreate, onOpenAdmin, onSelect, onToggleServer, onLogout, tasks, showDashboard = false }) {
  // 접근 가능한 인스턴스와 현재 백그라운드 작업을 함께 보여줍니다.
  const isEnglish = language === "en";
  const title = showDashboard ? (isEnglish ? "Server dashboard" : "서버 대시보드") : (isEnglish ? "Instances" : "인스턴스 목록");
  const description = showDashboard ? (isEnglish ? "Monitor system usage in real time." : "시스템 사용량을 실시간으로 확인하세요.") : (isEnglish ? "Manage Minecraft server instances." : "마인크래프트 서버 인스턴스를 관리하세요.");
  const createTitle = isEnglish ? "+ Create instance" : "+ 인스턴스 생성";
  const createDescription = isEnglish ? "Add a new Minecraft server." : "새 마인크래프트 서버를 추가합니다.";
  const createBadge = isEnglish ? "New" : "새 서버";
  const createAction = isEnglish ? "Create" : "생성";
  return (
    <main className="dashboard">
      <header className="page-header">
        <div>
          <p className="eyebrow">MARCHITECT</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        <div className="header-actions">
          <span className={`role-badge ${isAdmin ? "admin" : "user"}`}>{isAdmin ? "관리자" : "사용자"}</span>
          {isAdmin && !showDashboard && <button className="logout-button" type="button" onClick={onOpenAdmin}>Java 관리</button>}
          <button className="logout-button" type="button" onClick={onLogout}>로그아웃</button>
        </div>
      </header>

      {showDashboard && <ServerDashboard instances={instances} language={language} />}

      {showDashboard && tasks.length > 0 && <section className="management-section"><h2>백그라운드 작업</h2><ul className="runtime-list">{tasks.slice(0, 8).map((task) => <li key={task.id}><strong>{task.title}</strong><span>{task.status === "queued" ? "대기 중" : task.status === "running" ? task.indeterminate ? "NeoForge 설치 중" : `진행 중 ${task.progress}%` : task.status === "completed" ? "완료" : `실패: ${task.error}`}</span>{task.status === "running" && task.message && <small>{task.message}</small>}{(task.status === "queued" || task.status === "running") && (task.indeterminate ? <progress /> : <progress value={task.progress} max="100" />)}</li>)}</ul></section>}

      {!showDashboard && <section className="instances" aria-label="서버 목록">
        <div className="instance-list">
          {isAdmin && <article className="instance-row create-instance-row"><button className="instance-summary" type="button" onClick={onCreate}><span className="server-icon">+</span><span><strong>{createTitle}</strong><small>{createDescription}</small></span><span className="status create-status">{createBadge}</span><span className="chevron">›</span></button><button className="create-button" type="button" onClick={onCreate}>{createAction}</button></article>}
          {instances.map((instance) => (
            <InstanceCard key={instance.id} instance={instance} isAdmin={isAdmin} onSelect={onSelect} onToggleServer={onToggleServer} />
          ))}
        </div>
      </section>}
    </main>
  );
}

export default InstanceList;
