import { useCallback, useEffect, useRef, useState } from "react";
import api, { apiFileUrl, apiWebSocketUrl } from "../lib/api.js";
const NAV_ITEMS = [
  ["overview", "개요"],
  ["settings", "설정"],
  ["instance-settings", "인스턴스 설정"],
  ["access", "접근 관리"],
  ["logs", "로그"],
  ["world", "월드"],
];

function formatSize(size) {
  // 바이트 단위를 사람이 읽기 쉬운 파일 크기 문자열로 바꿉니다.
  if (size < 1024) return `${size} B`;
  if (size < 1024 ** 2) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 ** 2).toFixed(1)} MB`;
}

function canPreviewText(filename) {
  // 서버가 읽을 수 있는 일반적인 텍스트 확장자에만 보기 버튼을 표시합니다.
  return /\.(txt|log|json|properties|ya?ml|toml|cfg|conf|ini|sh|bat|md|csv|xml|html|js|py)$/i.test(filename);
}

function withoutMemoryJvmArgs(value) {
  // 메모리는 슬라이더에서만 관리하므로 직접 입력한 Xms/Xmx는 제거합니다.
  return value.replace(/(^|\s)-Xm[sx]\S+/g, "$1").replace(/\s+/g, " ").trim();
}

function InstanceDetail({ instance, isAdmin, language, onBack, onToggleServer, onDelete, onNotify, onLogout, onConfirm }) {
  // 선택한 인스턴스의 설정, 파일 목록과 현재 탭 상태를 관리합니다.
  const [activeTab, setActiveTab] = useState("overview");
  const [jvmArgs, setJvmArgs] = useState("");
  const [javaPath, setJavaPath] = useState("");
  const [javaVersion, setJavaVersion] = useState("");
  const [javaDistribution, setJavaDistribution] = useState("");
  const [memoryMb, setMemoryMb] = useState(2048);
  const [maxMemoryMb, setMaxMemoryMb] = useState(2048);
  const [javaRuntimes, setJavaRuntimes] = useState([]);
  const [launchMode, setLaunchMode] = useState("basic");
  const [customCommand, setCustomCommand] = useState("");
  const [launchTarget, setLaunchTarget] = useState("");
  const [launchKind, setLaunchKind] = useState("jar");
  const [instanceName, setInstanceName] = useState(instance.name);
  const [iconVersion, setIconVersion] = useState(instance.server_icon_updated_at || "");
  const [consoleLines, setConsoleLines] = useState([]);
  const [consoleInput, setConsoleInput] = useState("");
  const consoleSocket = useRef(null);
  const consoleOutput = useRef(null);
  const iconInput = useRef(null);
  const [properties, setProperties] = useState("");
  const [eula, setEula] = useState("");
  const [whitelist, setWhitelist] = useState([]);
  const [blacklist, setBlacklist] = useState([]);
  const [availableFiles, setAvailableFiles] = useState({ properties: false, eula: false, whitelist: false, blacklist: false });
  const [extensions, setExtensions] = useState({ mods: { exists: false }, plugins: { exists: false }, config: { exists: false } });
  const isRunning = instance.status === "running";
  const isEnglish = language === "en";
  const statusLabel = { running: "실행 중", stopped: "정지됨", starting: "시작 중", stopping: "정지 중" }[instance.status] ?? "정지됨";
  const javaVersions = [...new Set(javaRuntimes.map((runtime) => String(runtime.major_version)))];
  const javaDistributions = [...new Set(javaRuntimes.filter((runtime) => String(runtime.major_version) === javaVersion).map((runtime) => runtime.distribution || "OpenJDK"))];
  // 기본 모드에서 저장될 run.sh의 실제 실행 명령을 미리 보여줍니다.
  const previewCommand = (launchKind === "argfile"
    ? `${javaPath || "<Java 선택>"} -Xms${memoryMb}M -Xmx${memoryMb}M ${jvmArgs} @${launchTarget} nogui`
    : `${javaPath || "<Java 선택>"} -Xms${memoryMb}M -Xmx${memoryMb}M ${jvmArgs} -jar ${launchTarget} nogui`
  ).replace(/\s+/g, " ").trim();

  const loadDetailData = useCallback(async () => {
    // 상세 페이지에 필요한 설정과 파일 목록을 한 번에 불러옵니다.
    try {
      const [runtime, optionsResponse, propertiesResponse, eulaResponse, whitelistResponse, blacklistResponse, extensionsResponse] = await Promise.all([
        api.get(`/instances/${instance.id}/runtime`),
        api.get("/instances/system/runtime-options"),
        api.get(`/instances/${instance.id}/server-properties`),
        api.get(`/instances/${instance.id}/eula`),
        api.get(`/instances/${instance.id}/whitelist`),
        api.get(`/instances/${instance.id}/blacklist`),
        api.get(`/instances/${instance.id}/extensions`),
      ]);
      setJvmArgs(withoutMemoryJvmArgs(runtime.data.jvm_args));
      const selectedRuntime = optionsResponse.data.java_runtimes.find((item) => item.path === runtime.data.java_path) ?? optionsResponse.data.java_runtimes[0];
      setJavaPath(selectedRuntime?.path || runtime.data.java_path || "");
      setJavaVersion(selectedRuntime ? String(selectedRuntime.major_version) : "");
      setJavaDistribution(selectedRuntime?.distribution || "");
      setMemoryMb(runtime.data.memory_mb || 2048);
      setLaunchMode(runtime.data.launch_mode || "basic");
      setCustomCommand(runtime.data.custom_command || "");
      setLaunchTarget(runtime.data.launch_target || instance.jar_filename);
      setLaunchKind(runtime.data.launch_kind || "jar");
      setJavaRuntimes(optionsResponse.data.java_runtimes);
      setMaxMemoryMb(optionsResponse.data.max_memory_mb);
      setProperties(propertiesResponse.data.content);
      setEula(eulaResponse.data.content);
      setWhitelist(whitelistResponse.data.names);
      setBlacklist(blacklistResponse.data.names);
      setAvailableFiles({
        properties: propertiesResponse.data.exists,
        eula: eulaResponse.data.exists,
        whitelist: whitelistResponse.data.exists,
        blacklist: blacklistResponse.data.exists,
      });
      setExtensions(extensionsResponse.data);
    } catch {
      onNotify("인스턴스 상세 정보를 불러오지 못했습니다.", "error");
    }
  }, [instance.id, instance.jar_filename, onNotify]);

  useEffect(() => {
    loadDetailData();
  }, [loadDetailData]);

  useEffect(() => {
    // 서버 출력은 WebSocket으로 받고, 접속 중이 아닐 때도 백엔드가 로그 파일에 기록합니다.
    const socket = new WebSocket(apiWebSocketUrl(`/instances/${instance.id}/console`));
    consoleSocket.current = socket;
    socket.onmessage = (event) => { const data = JSON.parse(event.data); if (data.type === "log") setConsoleLines((lines) => [...lines, data.line].slice(-1000)); };
    return () => socket.close();
  }, [instance.id]);

  useEffect(() => {
    // 새 로그가 추가될 때마다 콘솔의 마지막 줄을 보이게 합니다.
    if (consoleOutput.current) consoleOutput.current.scrollTop = consoleOutput.current.scrollHeight;
  }, [consoleLines]);

  function sendConsoleCommand(event) {
    // 열린 WebSocket으로만 콘솔 명령어를 보내고, 전송한 입력값은 비웁니다.
    event.preventDefault();
    if (!consoleInput.trim() || consoleSocket.current?.readyState !== WebSocket.OPEN) return;
    consoleSocket.current.send(consoleInput); setConsoleInput("");
  }

  function selectJavaVersion(version) {
    // 선택한 Java 버전에 맞는 첫 런타임을 찾아 종류와 절대 경로를 함께 갱신합니다.
    const matching = javaRuntimes.find((runtime) => String(runtime.major_version) === version);
    setJavaVersion(version);
    setJavaDistribution(matching?.distribution || "");
    setJavaPath(matching?.path || "");
  }

  function selectJavaDistribution(distribution) {
    // 같은 Java 버전 안에서 배포판을 바꾸면 해당 런타임의 절대 경로를 적용합니다.
    const matching = javaRuntimes.find((runtime) => String(runtime.major_version) === javaVersion && (runtime.distribution || "OpenJDK") === distribution);
    setJavaDistribution(distribution);
    setJavaPath(matching?.path || "");
  }

  async function save(url, body, successMessage) {
    // 설정 파일 또는 목록 변경을 서버에 저장한 뒤 안내 문구를 표시합니다.
    try {
      const response = await api.put(`/instances/${instance.id}/${url}`, body);
      onNotify(successMessage);
      return response.data;
    } catch (requestError) {
      const detail = requestError.response?.data?.detail ?? "저장하지 못했습니다.";
      onNotify(detail, "error");
    }
  }

  async function changeServerState() {
    // 상위 앱에 서버 시작 또는 정지 요청을 전달합니다.
    try {
      if (instance.status !== "running") setConsoleLines([]);
      await onToggleServer(instance.id);
    } catch (requestError) {
      onNotify(requestError.response?.data?.detail ?? "서버 상태를 변경하지 못했습니다.", "error");
    }
  }

  async function forceStopServer() {
    // 정상 종료가 불가능할 때만 서버 프로세스를 강제로 종료합니다.
    if (!await onConfirm({ title: "서버 강제 종료", titleEn: "Force stop server", message: "서버를 강제 종료할까요? 저장되지 않은 데이터가 손상될 수 있습니다.", messageEn: "Force stop the server? Unsaved data may be damaged.", confirmLabel: "강제 종료", confirmLabelEn: "Force stop" })) return;
    await api.post(`/instances/${instance.id}/force-stop`);
    onNotify("서버를 강제 종료했습니다.");
  }

  async function uploadServerIcon(event) {
    // Validate and save the selected icon through the instance settings API.
    const iconFile = event.target.files?.[0];
    if (!iconFile) return;
    const formData = new FormData();
    formData.append("icon_file", iconFile);
    try {
      const response = await api.post(`/instances/${instance.id}/server-icon`, formData);
      setIconVersion(response.data.server_icon_updated_at);
      onNotify("서버 아이콘을 저장했습니다.");
    } catch (requestError) {
      onNotify(requestError.response?.data?.detail ?? "서버 아이콘을 저장하지 못했습니다.", "error");
    } finally {
      event.target.value = "";
    }
  }

  async function deleteThisInstance() {
    // 확인을 받은 뒤 인스턴스 전체 삭제를 상위 화면에 요청하고 목록으로 돌아갑니다.
    if (!await onConfirm({ title: "서버 삭제", titleEn: "Delete server", message: `"${instance.name}" 인스턴스와 내부 서버 파일을 모두 삭제할까요? 이 작업은 되돌릴 수 없습니다.`, messageEn: `Delete "${instance.name}" and all of its server files? This cannot be undone.`, confirmLabel: "삭제", confirmLabelEn: "Delete" })) return;
    if (await onDelete(instance.id)) onBack();
  }

  return (
    <main className={`dashboard detail-page ${activeTab === "overview" ? "console-active" : ""}`}>
      <div className="detail-topbar">
        <span />
        <button className="logout-button" type="button" onClick={onLogout}>로그아웃</button>
      </div>
      <section className="detail-card">
        <div className="detail-heading">
          <div>
            <span className={`status ${instance.status}`}>{statusLabel}</span>
            <h1>{instance.name}</h1>
            <p>{instance.jar_filename}</p>
          </div>
          <div className="header-actions"><button className={isRunning ? "stop-button" : "start-button"} type="button" disabled={instance.status === "starting" || instance.status === "stopping"} onClick={changeServerState}>{instance.status === "starting" ? "서버 시작 중..." : instance.status === "stopping" ? "서버 종료 중..." : isRunning ? "서버 정지" : "서버 시작"}</button>{isAdmin && (isRunning || instance.status === "starting" || instance.status === "stopping") && <button className="delete-button force-stop-button" type="button" onClick={forceStopServer}>강제 종료</button>}</div>
        </div>
      </section>


      {activeTab === "overview" && <section className="management-section console-section"><h2>서버 콘솔</h2><pre ref={consoleOutput} className="server-console">{consoleLines.join("\n") || "서버 로그를 기다리는 중입니다."}</pre>{isAdmin && <form className="console-input" onSubmit={sendConsoleCommand}><input value={consoleInput} onChange={(event) => setConsoleInput(event.target.value)} placeholder="서버 명령어 입력" /><button className="create-button" type="submit">전송</button></form>}</section>}

      {activeTab === "settings" && (<>
        <section className="management-section">
          <h2>실행 설정</h2>
          <div className="command-mode-toggle" role="group" aria-label="명령어 타입"><button className={launchMode === "basic" ? "active" : ""} type="button" disabled={!isAdmin} onClick={() => setLaunchMode("basic")}>기본</button><button className={launchMode === "custom" ? "active" : ""} type="button" disabled={!isAdmin} onClick={() => setLaunchMode("custom")}>커스텀</button></div>
          {launchMode === "custom" ? <><label htmlFor="custom-command">전체 시작 명령어</label><textarea id="custom-command" value={customCommand} onChange={(event) => setCustomCommand(event.target.value)} rows="4" disabled={!isAdmin} placeholder={isEnglish ? "e.g. /java/.../bin/java -Xmx2G -jar paper.jar nogui" : "예: /java/.../bin/java -Xmx2G -jar paper.jar nogui"} /></> : <><label htmlFor="java-version">Java 버전</label><select id="java-version" value={javaVersion} onChange={(event) => selectJavaVersion(event.target.value)} disabled={!isAdmin}>{javaVersions.map((version) => <option key={version} value={version}>Java {version}</option>)}</select><label htmlFor="java-distribution">Java 종류</label><select id="java-distribution" value={javaDistribution} onChange={(event) => selectJavaDistribution(event.target.value)} disabled={!isAdmin}>{javaDistributions.map((distribution) => <option key={distribution} value={distribution}>{distribution}</option>)}</select><label htmlFor="memory">{isEnglish ? `Memory: ${memoryMb} MB (max ${maxMemoryMb} MB)` : `메모리: ${memoryMb} MB (최대 ${maxMemoryMb} MB)`}</label><input id="memory" type="range" min="256" max={maxMemoryMb} step="256" value={Math.min(memoryMb, maxMemoryMb)} onChange={(event) => setMemoryMb(Number(event.target.value))} disabled={!isAdmin} /><label htmlFor="jvm-args">추가 JVM 인수</label><input id="jvm-args" value={jvmArgs} onChange={(event) => setJvmArgs(withoutMemoryJvmArgs(event.target.value))} placeholder={isEnglish ? "e.g. -Dfile.encoding=UTF-8" : "예: -Dfile.encoding=UTF-8"} disabled={!isAdmin} /><label htmlFor="launch-target">실행 파일 경로</label><input id="launch-target" value={launchTarget} onChange={(event) => setLaunchTarget(event.target.value)} placeholder={launchKind === "argfile" ? "libraries/.../unix_args.txt" : "server.jar"} disabled={!isAdmin} /></>}
          {launchMode === "basic" && <><label>최종 시작 명령어</label><code className="command-preview">{previewCommand}</code></>}
          {isAdmin && <button className="create-button" type="button" onClick={() => save("runtime", { java_path: javaPath, memory_mb: memoryMb, jvm_args: jvmArgs, launch_mode: launchMode, custom_command: customCommand, launch_target: launchTarget }, "실행 설정을 저장했습니다.")}>저장</button>}
        </section>
          <ConfigEditor title="server.properties" content={properties} onChange={setProperties} exists={availableFiles.properties} isAdmin={isAdmin} onSave={() => save("server-properties", { content: properties }, "server.properties를 저장했습니다.")} />
          <ConfigEditor title="eula.txt" content={eula} onChange={setEula} exists={availableFiles.eula} isAdmin={isAdmin} rows="4" onSave={() => save("eula", { content: eula }, "eula.txt를 저장했습니다.")} />
      </>)}

      {activeTab === "instance-settings" && <>
        <section className="management-section"><h2>서버 이름</h2><input value={instanceName} onChange={(event) => setInstanceName(event.target.value)} disabled={!isAdmin} />{isAdmin && <button className="create-button" type="button" onClick={() => save("name", { name: instanceName }, "서버 이름을 저장했습니다.")}>저장</button>}</section>
        <section className="management-section"><h2>서버 아이콘</h2><p className="section-description">64 × 64 픽셀 PNG 파일을 <code>server-icon.png</code>로 저장합니다.</p><div className="server-icon-upload">{iconVersion ? <img src={`${apiFileUrl(`/instances/${instance.id}/server-icon`)}?v=${encodeURIComponent(iconVersion)}`} alt="서버 아이콘 미리보기" /> : <span className="server-icon stopped">◆</span>}<input ref={iconInput} className="visually-hidden" type="file" accept="image/png,.png" onChange={uploadServerIcon} />{isAdmin && <button className="create-button" type="button" onClick={() => iconInput.current?.click()}>{isEnglish ? "Upload server-icon.png" : "server-icon.png 업로드"}</button>}</div></section>
        <section className="management-section danger-zone"><h2>서버 삭제</h2><p className="section-description">인스턴스와 월드, 모드, 플러그인 등 내부의 모든 파일을 삭제합니다.</p>{isAdmin && <button className="delete-button" type="button" onClick={deleteThisInstance}>서버 삭제</button>}</section>
      </>}

      {activeTab === "access" && (
        <section className="management-section">
          <NameListEditor title="화이트리스트" names={whitelist} setNames={setWhitelist} exists={availableFiles.whitelist} isAdmin={isAdmin} onSave={() => save("whitelist", { names: whitelist }, "화이트리스트를 저장했습니다.")} />
          <NameListEditor title="블랙리스트" names={blacklist} setNames={setBlacklist} exists={availableFiles.blacklist} isAdmin={isAdmin} onSave={() => save("blacklist", { names: blacklist }, "블랙리스트를 저장했습니다.")} />
        </section>
      )}

      {activeTab === "logs" && <FileBrowser instanceId={instance.id} area="logs" title={isEnglish ? "Log files" : "로그 파일"} isAdmin={isAdmin} onConfirm={onConfirm} />}
      {activeTab === "world" && <FileBrowser instanceId={instance.id} area="world" title={isEnglish ? "World files" : "월드 파일"} isAdmin={isAdmin} onConfirm={onConfirm} clearable directoryUpload beforeUpload={<a className="create-button" href={apiFileUrl(`/instances/${instance.id}/world/download`)}>{isEnglish ? "Download world ZIP" : "world 폴더 ZIP 다운로드"}</a>} />}
      {["mods", "plugins", "config"].includes(activeTab) && <FileBrowser instanceId={instance.id} area={activeTab} title={activeTab === "mods" ? isEnglish ? "Mods" : "모드" : activeTab === "plugins" ? isEnglish ? "Plugins" : "플러그인" : "Config"} isAdmin={isAdmin} onConfirm={onConfirm} clearable />}

      {isAdmin && <nav className="detail-nav" aria-label="인스턴스 상세 메뉴">
        {[...NAV_ITEMS, ...(extensions.mods.exists ? [["mods", "모드"]] : []), ...(extensions.plugins.exists ? [["plugins", "플러그인"]] : []), ...(extensions.config.exists ? [["config", "Config"]] : [])].map(([id, label]) => <button className={activeTab === id ? "active" : ""} type="button" key={id} onClick={() => setActiveTab(id)}>{label}</button>)}
      </nav>}
    </main>
  );
}

function ConfigEditor({ title, content, onChange, exists, isAdmin, rows = "12", onSave }) {
  // 서버가 생성한 텍스트 설정 파일을 편집하는 공통 화면입니다.
  return <section className="management-section"><h2>{title}</h2>{exists ? <><textarea value={content} onChange={(event) => onChange(event.target.value)} rows={rows} spellCheck="false" disabled={!isAdmin} />{isAdmin && <button className="create-button" type="button" onClick={onSave}>저장</button>}</> : <ConfigUnavailable />}</section>;
}

function NameListEditor({ title, names, setNames, exists, isAdmin, onSave }) {
  // 화이트리스트·블랙리스트 이름 목록을 편집하는 공통 화면입니다.
  const [query, setQuery] = useState(""); const [playerError, setPlayerError] = useState("");
  async function addPlayer() {
    // Mojang 프로필로 플레이어 이름을 검증한 뒤, 중복이 아니면 목록에 추가합니다.
    try {
      const response = await api.get(`/instances/players/${encodeURIComponent(query.trim())}`);
      if (!names.includes(response.data.name)) setNames([...names, response.data.name]);
      setQuery("");
      setPlayerError("");
    } catch (error) {
      setPlayerError(error.response?.data?.detail ?? "플레이어를 확인하지 못했습니다.");
    }
  }
  return <div className="player-manager"><h2>{title}</h2>{exists ? <><div className="console-input"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="플레이어 이름 검색" disabled={!isAdmin} />{isAdmin && <button className="create-button" type="button" onClick={addPlayer}>추가</button>}</div>{playerError && <p className="form-error">{playerError}</p>}<div className="player-cards">{names.filter(Boolean).map((name) => <article className="player-card" key={name}><img src={`https://mc-heads.net/avatar/${encodeURIComponent(name)}/48`} alt="" /><strong>{name}</strong>{isAdmin && <button className="delete-button" type="button" onClick={() => setNames(names.filter((item) => item !== name))}>삭제</button>}</article>)}</div>{isAdmin && <button className="create-button" type="button" onClick={onSave}>저장</button>}</> : <ConfigUnavailable />}</div>;
}

function ConfigUnavailable() {
  // 서버를 한 번도 시작하지 않아 설정 파일이 없을 때 안내합니다.
  return <p className="empty-message">서버를 한 번 시작하면 이 파일이 생성됩니다.</p>;
}

function FileBrowser({ instanceId, area, title, isAdmin, onConfirm, beforeUpload, clearable = false, directoryUpload = false }) {
  // 월드·모드·플러그인·로그 폴더를 같은 방식으로 탐색하고 관리합니다.
  const [currentPath, setCurrentPath] = useState("");
  const [entries, setEntries] = useState([]);
  const [exists, setExists] = useState(true);
  const [browserError, setBrowserError] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [textPreview, setTextPreview] = useState(null);
  const uploadInput = useRef(null);
  const directoryInput = useRef(null);

  const loadEntries = useCallback(async (path = currentPath) => {
    // 현재 경로의 직접 하위 파일·폴더 목록을 서버에서 새로 읽습니다.
    try {
      const response = await api.get(`/instances/${instanceId}/storage/${area}`, { params: { path } });
      setExists(response.data.exists);
      setEntries(response.data.entries);
      setBrowserError("");
    } catch (error) {
      setBrowserError(error.response?.data?.detail ?? "폴더 내용을 불러오지 못했습니다.");
    }
  }, [area, currentPath, instanceId]);

  useEffect(() => { setCurrentPath(""); }, [area, instanceId]);
  useEffect(() => { loadEntries(); }, [currentPath, loadEntries]);

  function goUp() {
    // 현재 폴더의 한 단계 위 경로로 이동합니다.
    setCurrentPath((path) => path.split("/").slice(0, -1).join("/"));
  }

  function downloadUrl(path) {
    // 경로의 각 부분을 인코딩해 파일 다운로드 주소를 만듭니다.
    return apiFileUrl(`/instances/${instanceId}/storage/${area}/${path.split("/").map(encodeURIComponent).join("/")}`);
  }

  async function previewText(entry) {
    // 텍스트로 안전하게 표시할 수 있는 파일의 내용을 미리 보기 창으로 불러옵니다.
    try {
      const encodedPath = entry.path.split("/").map(encodeURIComponent).join("/");
      const response = await api.get(`/instances/${instanceId}/storage/${area}/text/${encodedPath}`);
      setTextPreview(response.data);
    } catch (error) {
      setBrowserError(error.response?.data?.detail ?? "텍스트 파일을 읽지 못했습니다.");
    }
  }

  async function deleteEntry(entry) {
    // 확인을 받은 뒤 선택 파일 또는 폴더를 삭제하고 현재 목록을 갱신합니다.
    if (!await onConfirm({ title: "파일 삭제", titleEn: "Delete item", message: `${entry.type === "directory" ? "폴더와 내부 파일을 모두" : "파일을"} 삭제할까요?`, messageEn: entry.type === "directory" ? "Delete this folder and all files inside it?" : "Delete this file?", confirmLabel: "삭제", confirmLabelEn: "Delete" })) return;
    try {
      await api.delete(`/instances/${instanceId}/storage/${area}/${entry.path.split("/").map(encodeURIComponent).join("/")}`);
      await loadEntries();
    } catch (error) {
      setBrowserError(error.response?.data?.detail ?? "삭제하지 못했습니다.");
    }
  }

  async function clearDirectory() {
    // 관리 대상 최상위 폴더의 모든 내용을 삭제하고 목록을 처음 경로로 되돌립니다.
    if (!await onConfirm({ title: "폴더 비우기", titleEn: "Clear folder", message: `${title} 폴더 안의 모든 파일과 하위 폴더를 삭제할까요? 이 작업은 되돌릴 수 없습니다.`, messageEn: `Delete every file and subfolder in ${title}? This cannot be undone.`, confirmLabel: "전체 삭제", confirmLabelEn: "Clear all" })) return;
    try {
      await api.delete(`/instances/${instanceId}/storage/${area}`);
      setCurrentPath("");
      await loadEntries("");
    } catch (error) {
      setBrowserError(error.response?.data?.detail ?? "폴더를 비우지 못했습니다.");
    }
  }

  async function uploadFiles(event) {
    // 선택한 여러 파일을 현재 열어 둔 폴더에 업로드합니다. 같은 이름은 서버에서 덮어씁니다.
    const files = [...(event.target.files ?? [])];
    if (!files.length) return;
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    setIsUploading(true); setBrowserError("");
    try {
      await api.post(`/instances/${instanceId}/storage/${area}/upload`, formData, { params: { path: currentPath } });
      await loadEntries();
    } catch (error) {
      setBrowserError(error.response?.data?.detail ?? "파일을 업로드하지 못했습니다.");
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  async function uploadWorldDirectory(event) {
    // 브라우저가 제공한 상대 경로를 이용해 선택한 world 폴더 구조를 그대로 업로드합니다.
    const files = [...(event.target.files ?? [])];
    if (!files.length) return;
    const formData = new FormData();
    // Browser folder uploads provide this relative path for every child file.
    files.forEach((file) => formData.append("files", file, file.webkitRelativePath || file.name));
    setIsUploading(true); setBrowserError("");
    try {
      await api.post(`/instances/${instanceId}/storage/world/upload-directory`, formData, { params: { path: "" } });
      setCurrentPath("");
      await loadEntries("");
    } catch (error) {
      setBrowserError(error.response?.data?.detail ?? "world 폴더를 업로드하지 못했습니다.");
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  return <section className="management-section file-browser"><div className="file-browser-heading"><div><h2>{title}</h2><p className="file-path">/{currentPath}</p></div><div className="file-browser-buttons">{beforeUpload}{isAdmin && <>{clearable && <button className="delete-button" type="button" disabled={!exists || isUploading} onClick={clearDirectory}>전체 삭제</button>}<input ref={uploadInput} className="visually-hidden" type="file" multiple onChange={uploadFiles} />{directoryUpload && <><input ref={directoryInput} className="visually-hidden" type="file" multiple webkitdirectory="" onChange={uploadWorldDirectory} /><button className="cancel-button" type="button" disabled={!exists || isUploading} onClick={() => directoryInput.current?.click()}>world 폴더 업로드</button></>}<button className="create-button" type="button" disabled={!exists || isUploading} onClick={() => uploadInput.current?.click()}>{isUploading ? "업로드 중..." : "파일 업로드"}</button></>}</div></div>{browserError && <p className="form-error">{browserError}</p>}{!exists ? <p className="empty-message">서버를 한 번 실행하면 이 폴더가 생성됩니다.</p> : <><div className="file-browser-actions">{currentPath && <button className="cancel-button" type="button" onClick={goUp}>← 상위 폴더</button>}</div>{entries.length === 0 ? <p className="empty-message">이 폴더는 비어 있습니다.</p> : <ul className="file-list">{entries.map((entry) => <li key={entry.path} className={entry.type === "directory" ? "directory-entry" : ""}>{entry.type === "directory" ? <button className="directory-button" type="button" onClick={() => setCurrentPath(entry.path)}>📁 {entry.name}</button> : <><span>📄 {entry.name}</span><span className="file-size">{formatSize(entry.size)}</span>{canPreviewText(entry.name) && <button className="text-preview-button" type="button" onClick={() => previewText(entry)}>보기</button>}<a href={downloadUrl(entry.path)}>다운로드</a></>}{isAdmin && <button className="delete-button" type="button" onClick={() => deleteEntry(entry)}>삭제</button>}</li>)}</ul>}</>}{textPreview && <div className="text-preview-backdrop" role="presentation" onMouseDown={() => setTextPreview(null)}><article className="text-preview-modal" role="dialog" aria-modal="true" aria-label={`${textPreview.name} 내용`} onMouseDown={(event) => event.stopPropagation()}><div><h3>{textPreview.name}</h3><button className="cancel-button" type="button" onClick={() => setTextPreview(null)}>닫기</button></div><pre>{textPreview.content}</pre></article></div>}</section>;
}

export default InstanceDetail;
