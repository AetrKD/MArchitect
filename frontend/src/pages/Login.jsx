import { useState } from "react";

function Login({ onLogin }) {
  // 한 개의 접근 코드로 데모 역할을 선택하는 로그인 화면입니다.
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    // 입력한 접근 코드를 상위 인증 처리에 전달하고 실패하면 오류를 표시합니다.
    event.preventDefault();
    setIsSubmitting(true);
    setError("");
    if (await onLogin(code)) return;
    setError("유효하지 않은 접근 코드입니다.");
    setIsSubmitting(false);
  }

  return (
    <main className="login-page">
      <section className="login-card">
        <p className="eyebrow">MARCHITECT</p>
        <h1>서버 관리 로그인</h1>
        <p className="login-description">부여받은 접근 코드 하나를 입력해 계속하세요.</p>
        <form onSubmit={handleSubmit}>
          <label className="code-label" htmlFor="access-code">접근 코드</label>
          <input id="access-code" className="code-input" value={code} onChange={(event) => { setCode(event.target.value); setError(""); }} placeholder="접근 코드 입력" autoComplete="off" autoFocus />
          {error && <p className="login-error">{error}</p>}
          <button className="login-button" type="submit" disabled={isSubmitting}>{isSubmitting ? "확인 중..." : "입장하기"}</button>
        </form>
      </section>
    </main>
  );
}

export default Login;
