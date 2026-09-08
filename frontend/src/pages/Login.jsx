import { useState } from "react";
import { getMessages } from "../i18n/translations.js";

/** Authenticate one access code and expose preferences before sign-in. */
function Login({ language, theme, onLanguageChange, onThemeToggle, onLogin }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { sidebar } = getMessages(language);
  const isEnglish = language === "en";

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    if (await onLogin(code)) return;
    setError(isEnglish ? "Invalid access code." : "유효하지 않은 접근 코드입니다.");
    setIsSubmitting(false);
  }

  return <main className="login-page">
    <section className="login-card">
      <div className="login-preferences">
        <label htmlFor="login-language">{sidebar.language}</label>
        <select id="login-language" value={language} onChange={(event) => onLanguageChange(event.target.value)}><option value="ko">한국어</option><option value="en">English</option></select>
        <button type="button" onClick={onThemeToggle}>{theme === "dark" ? `☀ ${sidebar.lightMode}` : `◐ ${sidebar.darkMode}`}</button>
      </div>
      <p className="eyebrow">MARCHITECT</p>
      <h1>{isEnglish ? "Sign in to MArchitect" : "MArchitect 로그인"}</h1>
      <p className="login-description">{isEnglish ? "Enter your access code to sign in." : "접근 코드를 입력해 로그인하세요."}</p>
      <form onSubmit={handleSubmit}>
        <label className="code-label" htmlFor="access-code">{isEnglish ? "Access code" : "접근 코드"}</label>
        <input id="access-code" className="code-input" value={code} onChange={(event) => { setCode(event.target.value); setError(""); }} placeholder={isEnglish ? "Enter access code" : "접근 코드 입력"} autoComplete="off" autoFocus />
        {error && <p className="login-error">{error}</p>}
        <button className="login-button" type="submit" disabled={isSubmitting}>{isSubmitting ? (isEnglish ? "Checking..." : "확인 중...") : (isEnglish ? "Sign in" : "로그인")}</button>
      </form>
    </section>
  </main>;
}

export default Login;
