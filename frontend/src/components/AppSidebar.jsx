import { useState } from "react";

const LABELS = {
  ko: { home: "홈", instances: "인스턴스 목록", serverSettings: "서버 설정", users: "사용자 관리", java: "Java 관리", language: "언어", theme: "라이트 모드", admin: "관리자", user: "사용자" },
  en: { home: "Home", instances: "Instances", serverSettings: "Server settings", users: "Users", java: "Java runtimes", language: "Language", theme: "Light mode", admin: "Admin", user: "User" },
};

function AppSidebar({ path, role, language, theme, onLanguageChange, onThemeToggle, onNavigate }) {
  // 로그인 역할에 따라 접근 가능한 메뉴만 골라 공통 사이드바로 표시합니다.
  const [isOpen, setIsOpen] = useState(false);
  const labels = LABELS[language];
  const navigation = [["/dashboard", labels.home, "⌂"], ["/instances", labels.instances, "▤"], ...(role === "admin" ? [["/server-settings", labels.serverSettings, "⚙"], ["/users", labels.users, "♙"], ["/admin", labels.java, "☕"]] : [])];
  const subtitle = role === "admin" ? `${labels.admin.toUpperCase()} CONSOLE` : `${labels.user.toUpperCase()} CONSOLE`;
  function navigateAndClose(target) {
    // 메뉴 이동 뒤 모바일 사이드바를 닫아 콘텐츠 공간을 다시 확보합니다.
    onNavigate(target);
    setIsOpen(false);
  }
  return <aside className={`admin-sidebar ${isOpen ? "is-open" : ""}`}><button className="sidebar-mobile-toggle" type="button" aria-label="메뉴 열기 또는 닫기" aria-expanded={isOpen} onClick={() => setIsOpen((current) => !current)}>{isOpen ? "›" : "☰"}</button><div className="sidebar-brand"><strong>MARCHITECT</strong><span>{subtitle}</span></div><nav aria-label="주 메뉴">{navigation.map(([target, label, icon]) => <button className={path === target ? "active" : ""} type="button" key={target} onClick={() => navigateAndClose(target)}><span aria-hidden="true">{icon}</span>{label}</button>)}</nav><div className="sidebar-preferences"><label htmlFor="language-select">{labels.language}</label><select id="language-select" value={language} onChange={(event) => onLanguageChange(event.target.value)}><option value="ko">한국어</option><option value="en">English</option></select><button type="button" onClick={onThemeToggle}>{theme === "dark" ? `☀ ${labels.theme}` : "◐ Dark mode"}</button></div></aside>;
}

export default AppSidebar;
