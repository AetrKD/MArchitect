import { useState } from "react";
import { getMessages } from "../i18n/translations.js";

/** Render navigation and shared preferences for the signed-in user. */
function AppSidebar({ path, role, language, theme, onLanguageChange, onThemeToggle, onNavigate, onLogout }) {
  const [isOpen, setIsOpen] = useState(false);
  const { sidebar, common } = getMessages(language);
  const navigation = [["/dashboard", sidebar.home, "⌂"], ["/instances", sidebar.instances, "▣"], ...(role === "admin" ? [["/server-settings", sidebar.serverSettings, "⚙"], ["/users", sidebar.users, "♙"], ["/admin", sidebar.java, "☕"]] : [])];
  const subtitle = language === "en" ? (role === "admin" ? "Administrator console" : "User console") : (role === "admin" ? "관리자 콘솔" : "사용자 콘솔");
  function navigateAndClose(target) { onNavigate(target); setIsOpen(false); }
  function logoutAndClose() { onLogout(); setIsOpen(false); }
  return <aside className={`admin-sidebar ${isOpen ? "is-open" : ""}`}>
    <button className="sidebar-mobile-toggle" type="button" aria-label={sidebar.menuToggle} aria-expanded={isOpen} onClick={() => setIsOpen((current) => !current)}>{isOpen ? "›" : "☰"}</button>
    <div className="sidebar-brand"><strong>MARCHITECT</strong><span>{subtitle}</span></div>
    <nav aria-label={language === "en" ? "Main navigation" : "주 메뉴"}>{navigation.map(([target, label, icon]) => <button className={path === target ? "active" : ""} type="button" key={target} onClick={() => navigateAndClose(target)}><span aria-hidden="true">{icon}</span>{label}</button>)}</nav>
    <div className="sidebar-preferences"><label htmlFor="language-select">{sidebar.language}</label><select id="language-select" value={language} onChange={(event) => onLanguageChange(event.target.value)}><option value="ko">한국어</option><option value="en">English</option></select><button type="button" onClick={onThemeToggle}>{theme === "dark" ? `☀ ${sidebar.lightMode}` : `◐ ${sidebar.darkMode}`}</button><button className="logout-button sidebar-logout" type="button" onClick={logoutAndClose}>{common.logOut}</button></div>
  </aside>;
}

export default AppSidebar;
