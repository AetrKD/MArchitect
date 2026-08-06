import { useState } from "react";
import api from "../lib/api.js";

function ServerSettings({ onLogout, onNotify }) {
  // 관리자 코드 변경 폼의 세 입력값과 저장 중 상태를 관리합니다.
  const [currentCode, setCurrentCode] = useState("");
  const [newCode, setNewCode] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [isSaving, setIsSaving] = useState(false);

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

  return <main className="dashboard"><div className="detail-topbar management-topbar"><button className="logout-button" type="button" onClick={onLogout}>로그아웃</button></div><section className="detail-card"><p className="eyebrow">ADMIN</p><h1>서버 설정</h1><p>관리자 접근 코드를 변경합니다.</p></section><section className="management-section"><h2>관리자 코드 변경</h2><form className="instance-form" onSubmit={changeAdminCode}><label htmlFor="current-admin-code">현재 코드</label><input id="current-admin-code" type="password" value={currentCode} onChange={(event) => setCurrentCode(event.target.value)} required autoComplete="current-password" /><label htmlFor="new-admin-code">바뀔 코드</label><input id="new-admin-code" type="password" value={newCode} onChange={(event) => setNewCode(event.target.value)} minLength="8" required autoComplete="new-password" /><label htmlFor="confirm-admin-code">바뀔 코드 확인</label><input id="confirm-admin-code" type="password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} minLength="8" required autoComplete="new-password" /><button className="create-button" type="submit" disabled={isSaving}>{isSaving ? "저장 중..." : "변경 저장"}</button></form></section></main>;
}

export default ServerSettings;
