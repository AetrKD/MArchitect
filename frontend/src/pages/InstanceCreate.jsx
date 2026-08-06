import { useEffect, useState } from "react";
import api from "../lib/api.js";
const SERVER_TYPES = [["paper", "바닐라 (Paper)"], ["fabric", "Fabric"], ["neoforge", "NeoForge"], ["upload", "기타 (JAR 업로드)"]];

function InstanceCreate({ onCreate, onCancel, onLogout }) {
  // 생성 폼의 선택값과 다운로드 가능한 버전 목록을 관리합니다.
  const [name, setName] = useState("");
  const [sourceType, setSourceType] = useState("paper");
  const [minecraftVersions, setMinecraftVersions] = useState([]);
  const [minecraftVersion, setMinecraftVersion] = useState("");
  const [loaderVersions, setLoaderVersions] = useState([]);
  const [loaderVersion, setLoaderVersion] = useState("");
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    // Paper와 Fabric에서 수집한 공통 마인크래프트 버전을 한 번 불러옵니다.
    api.get("/server-catalog/minecraft-versions")
      .then((response) => setMinecraftVersions(response.data))
      .catch(() => setError("마인크래프트 버전 목록을 불러오지 못했습니다."));
  }, []);

  useEffect(() => {
    // 선택한 게임 버전에 맞는 Fabric 또는 NeoForge 로더만 다시 불러옵니다.
    setLoaderVersion("");
    setLoaderVersions([]);
    if ((sourceType !== "fabric" && sourceType !== "neoforge") || !minecraftVersion) return;
    const path = sourceType === "fabric" ? `fabric/loaders/${minecraftVersion}` : `neoforge/loaders/${minecraftVersion}`;
    api.get(`/server-catalog/${path}`)
      .then((response) => setLoaderVersions(response.data))
      .catch((requestError) => setError(requestError.response?.data?.detail ?? "선택한 마인크래프트 버전에 맞는 로더가 없습니다."));
  }, [sourceType, minecraftVersion]);

  async function handleSubmit(event) {
    // 필요한 값이 준비되었을 때 상위 앱에 인스턴스 생성을 요청합니다.
    event.preventDefault();
    if (sourceType === "upload" && !file) {
      setError("서버 JAR 파일을 선택해 주세요.");
      return;
    }
    setError(""); setIsSubmitting(true);
    try {
      await onCreate({ name: name.trim(), sourceType, file, minecraftVersion, loaderVersion, neoforgeVersion: null });
    } catch (requestError) {
      setError(requestError.response?.data?.detail ?? "인스턴스를 생성하지 못했습니다.");
      setIsSubmitting(false);
    }
  }

  return <main className="dashboard"><div className="detail-topbar"><button className="back-link" type="button" onClick={onCancel}>← 인스턴스 목록</button><button className="logout-button" type="button" onClick={onLogout}>로그아웃</button></div><section className="form-card"><p className="eyebrow">NEW INSTANCE</p><h1>인스턴스 생성</h1><p className="form-description">서버 유형을 먼저 선택하세요. 직접 JAR을 올리는 경우에는 버전 선택이 필요하지 않습니다.</p><form className="instance-form" onSubmit={handleSubmit}><label htmlFor="instance-name">서버 이름</label><input id="instance-name" value={name} onChange={(event) => setName(event.target.value)} required autoFocus /><label htmlFor="source-type">서버 유형</label><select id="source-type" value={sourceType} onChange={(event) => setSourceType(event.target.value)}>{SERVER_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>{sourceType === "upload" ? <><label htmlFor="instance-file">서버 JAR 파일</label><input id="instance-file" type="file" accept=".jar" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required /></> : <><VersionSelect label="마인크래프트 버전" id="minecraft-version" versions={minecraftVersions} value={minecraftVersion} onChange={setMinecraftVersion} />{sourceType === "fabric" && <VersionSelect label="Fabric Loader 버전" id="loader-version" versions={loaderVersions} value={loaderVersion} onChange={setLoaderVersion} />}{sourceType === "neoforge" && <VersionSelect label="NeoForge 로더 버전" id="loader-version" versions={loaderVersions} value={loaderVersion} onChange={setLoaderVersion} />}</>}{error && <p className="form-error">{error}</p>}<div className="form-actions"><button className="cancel-button" type="button" onClick={onCancel} disabled={isSubmitting}>취소</button><button className="create-button" type="submit" disabled={isSubmitting}>{isSubmitting ? "생성 중..." : "인스턴스 생성"}</button></div></form></section></main>;
}

function VersionSelect({ label, id, versions, value, onChange }) {
  // 버전 목록을 공통 선택 상자로 표시하고 목록을 받기 전에는 선택을 막습니다.
  return <><label htmlFor={id}>{label}</label><select id={id} value={value} onChange={(event) => onChange(event.target.value)} required disabled={versions.length === 0}><option value="">{versions.length === 0 ? "목록 불러오는 중..." : "버전 선택"}</option>{versions.map((version) => <option key={version} value={version}>{version}</option>)}</select></>;
}

export default InstanceCreate;
