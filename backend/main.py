"""FastAPI application entry point and router registration."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from modules.instances import router as instances_router
from modules.java_runtimes import router as java_runtimes_router
from modules.java_admin import router as java_admin_router
from modules.server_catalog import router as server_catalog_router
from modules.task_store import router as tasks_router
from modules.system_metrics import router as system_metrics_router
from modules.auth import initialize_auth_database, router as auth_router, session_role
from modules.domain_settings import router as domain_settings_router, sync_domain_settings

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_api_session(request: Request, call_next):
    """Require a valid session for every API route except login and health checks."""
    if request.method == "OPTIONS" or request.url.path in {"/", "/auth/login", "/docs", "/openapi.json"}:
        return await call_next(request)
    # 이미지와 파일 다운로드는 브라우저가 사용자 정의 헤더를 붙일 수 없으므로,
    # 읽기 전용 GET 요청에 한해 URL 토큰도 허용합니다.
    token = request.headers.get("X-MArchitect-Token")
    if request.method == "GET":
        token = token or request.query_params.get("token")
    role = session_role(token)
    if role not in {"admin", "user"}:
        return JSONResponse(status_code=401, content={"detail": "로그인이 필요합니다."})
    request.state.role = role
    return await call_next(request)

app.include_router(instances_router)
app.include_router(java_runtimes_router)
app.include_router(java_admin_router)
app.include_router(server_catalog_router)
app.include_router(tasks_router)
app.include_router(system_metrics_router)
app.include_router(auth_router)
app.include_router(domain_settings_router)


@app.on_event("startup")
async def prepare_auth_database():
    """서버 시작 전에 접근 코드용 SQLite 데이터베이스를 준비합니다."""
    await initialize_auth_database()
    sync_domain_settings()


@app.get("/")
async def root():
    """백엔드가 정상적으로 실행 중인지 확인하는 응답을 반환합니다."""
    return {"message": "MArchitect API is running"}
