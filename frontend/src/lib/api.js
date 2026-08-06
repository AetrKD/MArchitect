import axios from "axios";

// 모든 화면이 같은 백엔드 주소를 사용하도록 한 곳에서 관리합니다.
// The reverse proxy exposes FastAPI below this path in every environment.
const API_BASE_URL = "/api";

// FastAPI 요청에 사용하는 공통 HTTP 클라이언트입니다.
const api = axios.create({ baseURL: API_BASE_URL });
let sessionToken = null;

export function setAuthToken(token) {
  // 로그인 세션 토큰을 모든 백엔드 요청의 헤더에 적용하거나 제거합니다.
  sessionToken = token || null;
  if (sessionToken) api.defaults.headers.common["X-MArchitect-Token"] = sessionToken;
  else delete api.defaults.headers.common["X-MArchitect-Token"];
}

/** 서버가 제공하는 파일을 내려받을 때 사용할 전체 URL을 만듭니다. */
export function apiFileUrl(path) {
  // img, a 다운로드 요청은 Axios 헤더를 사용할 수 없으므로 세션 토큰을 URL에 덧붙입니다.
  // 백엔드는 GET 요청에서만 이 토큰을 허용합니다.
  const separator = path.includes("?") ? "&" : "?";
  const tokenQuery = sessionToken ? `${separator}token=${encodeURIComponent(sessionToken)}` : "";
  return `${API_BASE_URL}${path}${tokenQuery}`;
}

export function apiWebSocketUrl(path) {
  // Keep WebSocket traffic on the browser's current host and protocol.
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const separator = path.includes("?") ? "&" : "?";
  const tokenQuery = sessionToken ? `${separator}token=${encodeURIComponent(sessionToken)}` : "";
  return `${protocol}//${window.location.host}${API_BASE_URL}${path}${tokenQuery}`;
}

export default api;
