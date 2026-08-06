import axios from "axios";

// 모든 화면이 같은 백엔드 주소를 사용하도록 한 곳에서 관리합니다.
// The reverse proxy exposes FastAPI below this path in every environment.
const API_BASE_URL = "/api";

// FastAPI 요청에 사용하는 공통 HTTP 클라이언트입니다.
const api = axios.create({ baseURL: API_BASE_URL });

export function setAuthToken(token) {
  // 로그인 세션 토큰을 모든 백엔드 요청의 헤더에 적용하거나 제거합니다.
  if (token) api.defaults.headers.common["X-MArchitect-Token"] = token;
  else delete api.defaults.headers.common["X-MArchitect-Token"];
}

/** 서버가 제공하는 파일을 내려받을 때 사용할 전체 URL을 만듭니다. */
export function apiFileUrl(path) {
  return `${API_BASE_URL}${path}`;
}

export function apiWebSocketUrl(path) {
  // Keep WebSocket traffic on the browser's current host and protocol.
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${API_BASE_URL}${path}`;
}

export default api;
