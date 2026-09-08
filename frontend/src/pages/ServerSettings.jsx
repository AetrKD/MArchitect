import { useEffect, useState } from "react";
import api from "../lib/api.js";

function ServerSettings({ onLogout, onNotify }) {
  // 관리자 코드 변경 폼의 세 입력값과 저장 중 상태를 관리합니다.
  const [currentCode, setCurrentCode] = useState("");
  const [newCode, setNewCode] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [domains, setDomains] = useState("");
  const [domainsLoaded, setDomainsLoaded] = useState(false);
  const [domainError, setDomainError] = useState("");
  const [savingDomains, setSavingDomains] = useState(false);

  useEffect(() => {
    let active = true;
    api.get("/settings/domains").then(({ data }) => {
      if (active) { setDomains(data.domains.join("\n")); setDomainsLoaded(true); }
    }).catch(() => {
      if (active) setDomainError("접속 주소를 불러오지 못했습니다. 페이지를 새로고침해 주세요.");
    });
    return () => { active = false; };
  }, []);

  async function saveDomains(event) {
    event.preventDefault();
    setSavingDomains(true);
    setDomainError("");
    try {
      const { data } = await api.put("/settings/domains", {
        domains: domains.split(/[\n,]/).map((host) => host.trim()).filter(Boolean),
      });
      setDomains(data.domains.join("\n"));
      onNotify("접속 주소를 저장했습니다.");
    } catch (error) {
      const detail = error.response?.data?.detail;
      setDomainError(typeof detail === "string" ? detail : "입력한 주소를 확인해 주세요. https://, 포트 번호, 경로는 제외하세요.");
    } finally {
      setSavingDomains(false);
    }
  }

  async function changeAdminCode(event) {
    // 현재 코드 검증과 새 코드 확인을 백엔드에 요청한 뒤 성공하면 폼을 비웁니다.
    event.preventDefault();
    setIsSaving(true);
    try {
      await api.put("/auth/admin-code", { current_code: currentCode, new_code: newCode, confirmation });
      setCurrentCode("");
      setNewCode("");
      setConfirmation("");
      onNotify("관리자 코드를 변경했습니다.");
    } catch (error) {
      onNotify(error.response?.data?.detail ?? "관리자 코드를 변경하지 못했습니다.", "error");
    } finally {
      setIsSaving(false);
    }
  }

  return <main className="dashboard"><div className="detail-topbar management-topbar"><button className="logout-button" type="button" onClick={onLogout}>로그아웃</button></div><section className="detail-card"><p className="eyebrow">ADMIN</p><h1>서버 설정</h1><p>관리자 접근 코드와 웹 콘솔 접속 주소를 관리하세요.</p></section><section className="management-section"><h2>관리자 코드 변경</h2><form className="instance-form" onSubmit={changeAdminCode}><label htmlFor="current-admin-code">현재 코드</label><input id="current-admin-code" type="password" value={currentCode} onChange={(event) => setCurrentCode(event.target.value)} required autoComplete="current-password" /><label htmlFor="new-admin-code">새 코드</label><input id="new-admin-code" type="password" value={newCode} onChange={(event) => setNewCode(event.target.value)} minLength="8" required autoComplete="new-password" /><label htmlFor="confirm-admin-code">새 코드 확인</label><input id="confirm-admin-code" type="password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} minLength="8" required autoComplete="new-password" /><button className="create-button" type="submit" disabled={isSaving}>{isSaving ? "저장 중..." : "변경 저장"}</button></form></section><section className="management-section"><h2>접속 주소 설정</h2><p>웹 콘솔에 사용할 도메인이나 IP 주소를 등록하세요. 도메인 연결과 HTTPS 설정은 별도로 필요합니다.</p><form className="instance-form" onSubmit={saveDomains}><label htmlFor="allowed-domains">도메인 / IP 주소</label><textarea id="allowed-domains" rows={4} value={domains} onChange={(event) => setDomains(event.target.value)} placeholder="panel.example.com" aria-describedby="domain-help" disabled={!domainsLoaded || savingDomains} /><p id="domain-help">주소를 한 줄에 하나씩 입력하세요. 저장한 목록은 재시작 후에도 유지됩니다. 모두 지워도 IP 주소로 접속할 수 있습니다.</p><p>이 목록은 접속자를 제한하지 않습니다. 운영용 설치에서는 주소 등록 없이도 접속할 수 있습니다.</p>{domainError && <p role="alert">{domainError}</p>}<button className="create-button" type="submit" disabled={!domainsLoaded || savingDomains}>{savingDomains ? "저장 중..." : "접속 주소 저장"}</button></form></section></main>;
}

export default ServerSettings;
