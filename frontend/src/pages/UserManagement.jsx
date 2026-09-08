import { useCallback, useEffect, useState } from "react";
import api from "../lib/api.js";

function UserManagement({ onLogout, onNotify, onConfirm }) {
  // 발급된 사용자 코드 목록, 방금 발급한 원본 코드와 로딩 상태를 관리합니다.
  const [codes, setCodes] = useState([]);
  const [issuedCode, setIssuedCode] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isIssuing, setIsIssuing] = useState(false);

  const loadCodes = useCallback(async () => {
    // 관리자가 삭제할 수 있도록 마스킹된 사용자 코드 목록을 불러옵니다.
    setIsLoading(true);
    try {
      const response = await api.get("/auth/user-codes");
      setCodes(response.data);
    } catch (error) {
      onNotify(error.response?.data?.detail ?? "사용자 코드 목록을 불러오지 못했습니다.", "error");
    } finally {
      setIsLoading(false);
    }
  }, [onNotify]);

  useEffect(() => {
    // 화면에 들어오면 최신 사용자 코드 목록을 표시합니다.
    loadCodes();
  }, [loadCodes]);

  async function issueCode() {
    // 새 사용자 접근 코드를 발급하고 원본은 관리자에게 한 번만 표시합니다.
    setIsIssuing(true);
    try {
      const response = await api.post("/auth/user-codes");
      setIssuedCode(response.data.code);
      setCodes((current) => [response.data, ...current]);
      onNotify("새 사용자 코드를 발급했습니다.");
    } catch (error) {
      onNotify(error.response?.data?.detail ?? "사용자 코드를 발급하지 못했습니다.", "error");
    } finally {
      setIsIssuing(false);
    }
  }

  async function deleteCode(code) {
    // 확인 후 선택한 사용자 접근 코드를 삭제하고 화면 목록에서도 제거합니다.
    if (!await onConfirm({ title: "사용자 코드 삭제", titleEn: "Delete user code", message: `${code.hint} 코드를 삭제할까요?`, messageEn: `Delete the ${code.hint} code?`, confirmLabel: "삭제", confirmLabelEn: "Delete" })) return;
    try {
      await api.delete(`/auth/user-codes/${code.id}`);
      setCodes((current) => current.filter((item) => item.id !== code.id));
      onNotify("사용자 코드를 삭제했습니다.");
    } catch (error) {
      onNotify(error.response?.data?.detail ?? "사용자 코드를 삭제하지 못했습니다.", "error");
    }
  }

  return <main className="dashboard"><div className="detail-topbar management-topbar"><button className="logout-button" type="button" onClick={onLogout}>로그아웃</button></div><section className="detail-card"><p className="eyebrow">ADMIN</p><h1>사용자 관리</h1><p>다른 사람에게 전달할 로그인 코드를 발급하거나 삭제하세요.</p></section>{issuedCode && <section className="management-section"><h2>새로 발급한 사용자 코드</h2><code className="command-preview">{issuedCode}</code><p className="section-description">전체 코드는 지금만 표시됩니다. 안전한 곳에 보관하고 사용할 사람에게 전달하세요.</p></section>}<section className="management-section"><div className="file-browser-heading"><h2>사용자 코드</h2><button className="create-button" type="button" onClick={issueCode} disabled={isIssuing}>{isIssuing ? "발급 중..." : "새 사용자 코드 발급"}</button></div>{isLoading ? <p className="empty-message">사용자 코드 목록을 불러오는 중입니다.</p> : codes.length === 0 ? <p className="empty-message">발급된 사용자 코드가 없습니다.</p> : <ul className="runtime-list">{codes.map((code) => <li key={code.id}><strong>{code.hint}</strong><span>{new Date(code.created_at).toLocaleString()}</span><button className="delete-button" type="button" onClick={() => deleteCode(code)}>삭제</button></li>)}</ul>}</section></main>;
}

export default UserManagement;
