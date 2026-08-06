import { useCallback, useEffect, useState } from "react";
import api from "../lib/api.js";

function AdminRuntime({ onLogout, onNotify }) {
  // Java 목록, 선택 버전, 현재 설치 작업 상태를 관리합니다.
  const [available, setAvailable] = useState([]);
  const [installed, setInstalled] = useState([]);
  const [selectedVersion, setSelectedVersion] = useState("");
  const [activeTask, setActiveTask] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadRuntimes = useCallback(async () => {
    // 설치 가능한 Temurin 버전과 현재 감지된 런타임을 함께 갱신합니다.
    setIsLoading(true);
    try {
      const [availableResponse, installedResponse] = await Promise.all([
        api.get("/admin/java-runtimes/available"),
        api.get("/admin/java-runtimes"),
      ]);
      setAvailable(availableResponse.data);
      setInstalled(installedResponse.data);
      setSelectedVersion((current) => current || String(availableResponse.data.at(-1) ?? ""));
    } catch {
      onNotify("Temurin Java 정보를 불러오지 못했습니다.", "error");
    } finally {
      setIsLoading(false);
    }
  }, [onNotify]);

  useEffect(() => {
    // 페이지를 열면 Java 정보를 불러옵니다.
    loadRuntimes();
  }, [loadRuntimes]);

  useEffect(() => {
    // 진행 중인 설치 작업만 주기적으로 확인하고 결과는 토스트로 알립니다.
    if (!activeTask || activeTask.deleting) return undefined;
    const intervalId = window.setInterval(async () => {
      try {
        const { data: task } = await api.get(`/tasks/${activeTask.id}`);
        if (task.status === "completed") {
          onNotify(`${task.title} 완료`);
          setActiveTask(null);
          await loadRuntimes();
        } else if (task.status === "failed") {
          onNotify(`${task.title}: ${task.error || "실패했습니다."}`, "error");
          setActiveTask(null);
        }
      } catch {
        setActiveTask(null);
      }
    }, 1500);
    return () => window.clearInterval(intervalId);
  }, [activeTask, loadRuntimes, onNotify]);

  async function installRuntime() {
    // 드롭다운에서 선택한 Java 버전을 백그라운드 설치 작업으로 등록합니다.
    const majorVersion = Number(selectedVersion);
    if (!majorVersion) return;
    try {
      const { data: task } = await api.post("/admin/java-runtimes/download", { major_version: majorVersion });
      setActiveTask(task);
      onNotify(`Java ${majorVersion} 다운로드를 시작했습니다.`, "info");
    } catch (error) {
      onNotify(error.response?.data?.detail ?? "Java를 다운로드하지 못했습니다.", "error");
    }
  }

  async function deleteRuntime(runtime) {
    // 앱이 관리하는 Java 폴더만 확인 후 삭제하고 목록을 갱신합니다.
    if (!window.confirm(`${runtime.name} 런타임을 삭제할까요?`)) return;
    setActiveTask({ id: runtime.managed_directory, deleting: true });
    try {
      await api.delete(`/admin/java-runtimes/${encodeURIComponent(runtime.managed_directory)}`);
      onNotify(`${runtime.name} 런타임을 삭제했습니다.`);
      await loadRuntimes();
    } catch (error) {
      onNotify(error.response?.data?.detail ?? "Java 런타임을 삭제하지 못했습니다.", "error");
    } finally {
      setActiveTask(null);
    }
  }

  const installedVersions = new Set(installed.map((runtime) => String(runtime.major_version)));
  const isBusy = Boolean(activeTask);
  const isInstalled = installedVersions.has(selectedVersion);

  if (isLoading) return <RuntimeLoading onLogout={onLogout} />;

  return <main className="dashboard">
    <RuntimeTopBar onLogout={onLogout} />
    <section className="detail-card"><p className="eyebrow">ADMIN</p><h1>Java 런타임 관리</h1><p>Temurin Linux x64 JDK를 프로젝트 JAVA 폴더에 설치합니다.</p></section>
    <InstalledRuntimes runtimes={installed} isBusy={isBusy} activeTask={activeTask} onDelete={deleteRuntime} />
    <section className="management-section"><h2>Temurin Linux x64 다운로드</h2><div className="runtime-buttons"><select aria-label="설치할 Java 버전" value={selectedVersion} onChange={(event) => setSelectedVersion(event.target.value)} disabled={isBusy || available.length === 0}>{available.map((version) => <option key={version} value={version}>Java {version}{installedVersions.has(String(version)) ? " (설치됨)" : ""}</option>)}</select><button className="create-button" type="button" disabled={!selectedVersion || isBusy || isInstalled} onClick={installRuntime}>{isInstalled ? "이미 설치됨" : isBusy ? "설치 중..." : "설치"}</button></div></section>
  </main>;
}

function RuntimeTopBar({ onLogout }) {
  // 공통 페이지 상단에는 사이드바와 중복되는 뒤로 가기 버튼을 두지 않습니다.
  return <div className="detail-topbar management-topbar"><button className="logout-button" type="button" onClick={onLogout}>로그아웃</button></div>;
}

function RuntimeLoading({ onLogout }) {
  // 런타임 API 응답 전에는 레이아웃이 흔들리지 않는 로딩 화면을 표시합니다.
  return <main className="dashboard"><RuntimeTopBar onLogout={onLogout} /><section className="loading-screen" role="status"><span className="loading-spinner" aria-hidden="true" /><h1>Java 런타임 정보를 불러오는 중입니다.</h1><p>설치된 Java와 다운로드 가능한 버전을 확인하고 있습니다.</p></section></main>;
}

function InstalledRuntimes({ runtimes, isBusy, activeTask, onDelete }) {
  // 설치된 런타임 목록과 각 항목의 삭제 동작을 표시합니다.
  return <section className="management-section"><h2>설치된 런타임</h2>{runtimes.length === 0 ? <p className="empty-message">감지된 Java 런타임이 없습니다.</p> : <ul className="runtime-list">{runtimes.map((runtime) => <li key={runtime.id}><strong>{runtime.name}</strong><span>{runtime.version}</span><code>{runtime.path}</code>{runtime.managed_directory && <button className="delete-button" type="button" disabled={isBusy} onClick={() => onDelete(runtime)}>{activeTask?.deleting && activeTask.id === runtime.managed_directory ? "삭제 중..." : "삭제"}</button>}</li>)}</ul>}</section>;
}

export default AdminRuntime;
