import { useCallback, useEffect, useRef, useState } from "react";
import api, { setAuthToken } from "./lib/api.js";
import AdminRuntime from "./pages/AdminRuntime.jsx";
import InstanceCreate from "./pages/InstanceCreate.jsx";
import InstanceDetail from "./pages/InstanceDetail.jsx";
import InstanceList from "./pages/InstanceList.jsx";
import Login from "./pages/Login.jsx";
import ServerSettings from "./pages/ServerSettings.jsx";
import UserManagement from "./pages/UserManagement.jsx";
import AppSidebar from "./components/AppSidebar.jsx";
import ToastNotifications from "./components/ToastNotifications.jsx";
import { translate } from "./i18n/translations.js";
import "./App.css";

function App() {
  // 로그인 역할, 화면 경로, 인스턴스·작업 데이터와 전역 알림을 관리합니다.
  const [instances, setInstances] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [toasts, setToasts] = useState([]);
  const [role, setRole] = useState(null);
  const [path, setPath] = useState(window.location.pathname);
  const [language, setLanguage] = useState(() => window.localStorage.getItem("marchitect-language") || "ko");
  const [theme, setTheme] = useState(() => window.localStorage.getItem("marchitect-theme") || "dark");
  const taskStates = useRef(new Map());
  const selectedInstanceId = path.match(/^\/instances\/([^/]+)$/)?.[1];
  const selectedInstance = instances.find((instance) => String(instance.id) === selectedInstanceId);

  const notify = useCallback((message, type = "success") => {
    // 새 알림을 추가하고 4초 뒤 같은 알림만 자동으로 제거합니다.
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((current) => [...current.slice(-3), { id, message, type }]);
    window.setTimeout(() => setToasts((current) => current.filter((toast) => toast.id !== id)), 4000);
  }, []);

  useEffect(() => {
    // 선택한 언어와 테마를 브라우저에 저장하고 문서 전체에 테마를 적용합니다.
    window.localStorage.setItem("marchitect-language", language);
    window.localStorage.setItem("marchitect-theme", theme);
    document.documentElement.dataset.theme = theme;
  }, [language, theme]);

  useEffect(() => {
    // 아직 번역 키로 바꾸지 않은 기존 화면 문구도 언어 파일로 일관되게 치환합니다.
    const translateNode = (node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        const translated = translate(language, node.nodeValue);
        if (translated !== node.nodeValue) node.nodeValue = translated;
        return;
      }
      if (node.nodeType !== Node.ELEMENT_NODE || ["SCRIPT", "STYLE"].includes(node.tagName)) return;
      ["placeholder", "aria-label", "title"].forEach((attribute) => {
        if (node.hasAttribute(attribute)) node.setAttribute(attribute, translate(language, node.getAttribute(attribute)));
      });
      node.childNodes.forEach(translateNode);
    };
    translateNode(document.body);
    const observer = new MutationObserver((mutations) => mutations.forEach((mutation) => {
      if (mutation.type === "characterData") translateNode(mutation.target);
      mutation.addedNodes.forEach(translateNode);
    }));
    observer.observe(document.body, { childList: true, characterData: true, subtree: true });
    return () => observer.disconnect();
  }, [language]);

  useEffect(() => {
    // 브라우저의 뒤로·앞으로 이동 후 주소를 React 상태에 반영합니다.
    function handlePopState() {
      setPath(window.location.pathname);
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    // 로그인 중에만 인스턴스 상태와 리소스 정보를 2초마다 갱신합니다.
    if (!role) {
      setInstances([]);
      return undefined;
    }
    async function loadInstances() {
      // 목록과 상태를 최신 서버 응답으로 교체합니다.
      try {
        const response = await api.get("/instances");
        setInstances(response.data);
      } catch (error) {
        console.error("인스턴스 목록을 불러오지 못했습니다.", error);
      }
    }
    loadInstances();
    const intervalId = window.setInterval(loadInstances, 2000);
    return () => window.clearInterval(intervalId);
  }, [role]);

  useEffect(() => {
    // 백그라운드 작업 진행 상태를 갱신하고 상태 변화는 토스트로 알립니다.
    if (!role) {
      setTasks([]);
      return undefined;
    }
    async function loadTasks() {
      // 새 작업, 완료, 실패, 진행 구간 변화를 확인합니다.
      try {
        const response = await api.get("/tasks");
        setTasks(response.data);
        const nextStates = new Map();
        response.data.forEach((task) => {
          const previous = taskStates.current.get(task.id);
          nextStates.set(task.id, { status: task.status, progress: task.progress });
          if (!previous && task.status === "running") notify(`${task.title}: 작업을 시작했습니다.`, "info");
          if (previous && previous.status !== "completed" && task.status === "completed") notify(`${task.title}: 완료되었습니다.`);
          if (previous && previous.status !== "failed" && task.status === "failed") notify(`${task.title}: ${task.error || "실패했습니다."}`, "error");
        });
        taskStates.current = nextStates;
      } catch (error) {
        console.error("작업 상태를 불러오지 못했습니다.", error);
      }
    }
    loadTasks();
    const intervalId = window.setInterval(loadTasks, 2000);
    return () => window.clearInterval(intervalId);
  }, [role, notify]);

  function navigate(nextPath) {
    // 별도 라우터 없이 주소와 화면 상태를 함께 이동합니다.
    window.history.pushState({}, "", nextPath);
    setPath(nextPath);
  }

  async function login(code) {
    // 백엔드에서 접근 코드를 검증하고 세션 토큰과 역할을 적용합니다.
    try {
      const response = await api.post("/auth/login", { code });
      setAuthToken(response.data.token);
      setRole(response.data.role);
      navigate("/dashboard");
      return true;
    } catch {
      return false;
    }
  }

  function logout() {
    // 메모리에만 둔 세션 토큰과 역할을 지우고 로그인 화면으로 돌아갑니다.
    setAuthToken(null);
    setRole(null);
    navigate("/");
  }

  function withAppChrome(page) {
    // 로그인한 역할에 맞는 사이드바와 전역 토스트를 모든 화면에 함께 표시합니다.
    const content = <div className="admin-shell"><AppSidebar path={path} role={role} language={language} theme={theme} onLanguageChange={setLanguage} onThemeToggle={() => setTheme((current) => current === "dark" ? "light" : "dark")} onNavigate={navigate} /><div className="admin-page">{page}</div></div>;
    return <>{content}<ToastNotifications toasts={toasts} /></>;
  }

  async function createInstance({ name, sourceType, file, minecraftVersion, loaderVersion, neoforgeVersion }) {
    // 업로드 또는 공식 카탈로그 방식으로 인스턴스 생성을 요청합니다.
    let response;
    if (sourceType === "upload") {
      const formData = new FormData();
      formData.append("name", name);
      formData.append("jar_file", file);
      response = await api.post("/instances", formData);
      setInstances((current) => [...current, response.data]);
      navigate(`/instances/${response.data.id}`);
      return;
    }
    response = await api.post("/instances/download", { name, source_type: sourceType, minecraft_version: minecraftVersion || null, loader_version: loaderVersion || null, neoforge_version: sourceType === "neoforge" ? loaderVersion || neoforgeVersion || null : null });
    setTasks((current) => [response.data, ...current]);
    navigate("/instances");
  }

  async function toggleServer(id) {
    // 로그인한 사용자가 선택한 인스턴스의 현재 상태에 따라 시작 또는 정지를 요청합니다.
    const instance = instances.find((current) => current.id === id);
    const action = instance?.status === "running" ? "stop" : "start";
    const response = await api.post(`/instances/${id}/${action}`);
    setInstances((current) => current.map((item) => item.id === id ? response.data : item));
  }

  async function deleteInstance(id) {
    // 관리자가 인스턴스 삭제를 요청하고 성공 시 목록에서도 제거합니다.
    if (role !== "admin") return false;
    try {
      await api.delete(`/instances/${id}`);
      setInstances((current) => current.filter((instance) => instance.id !== id));
      return true;
    } catch (error) {
      notify(error.response?.data?.detail ?? "인스턴스를 삭제하지 못했습니다.", "error");
      return false;
    }
  }

  if (!role) return <Login onLogin={login} />;
  if (path === "/instances/new" && role === "admin") return withAppChrome(<InstanceCreate onCreate={createInstance} onCancel={() => navigate("/instances")} onLogout={logout} />);
  if (path === "/admin" && role === "admin") return withAppChrome(<AdminRuntime onLogout={logout} onNotify={notify} />);
  if (path === "/server-settings" && role === "admin") return withAppChrome(<ServerSettings onLogout={logout} onNotify={notify} />);
  if (path === "/users" && role === "admin") return withAppChrome(<UserManagement onLogout={logout} onNotify={notify} />);
  if (selectedInstance) return withAppChrome(<InstanceDetail instance={selectedInstance} isAdmin={role === "admin"} onBack={() => navigate("/instances")} onToggleServer={toggleServer} onDelete={deleteInstance} onNotify={notify} onLogout={logout} />);
  return withAppChrome(<InstanceList instances={instances} isAdmin={role === "admin"} language={language} onCreate={() => navigate("/instances/new")} onOpenAdmin={() => navigate("/admin")} onSelect={(id) => navigate(`/instances/${id}`)} onToggleServer={toggleServer} onLogout={logout} tasks={tasks} showDashboard={path === "/dashboard"} />);
}

export default App;
