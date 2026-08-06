"""접근 코드 로그인과 관리자 전용 코드 관리를 제공하는 API입니다."""
import hashlib
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/auth", tags=["auth"])
AUTH_DATABASE = Path(os.getenv("MARCHITECT_AUTH_DB", "/data/marchitect.sqlite3"))
INITIAL_ADMIN_CODE = os.getenv("MARCHITECT_INITIAL_ADMIN_CODE", "ADMIN")
INITIAL_USER_CODE = os.getenv("MARCHITECT_INITIAL_USER_CODE", "")
SESSIONS: dict[str, str] = {}


class LoginRequest(BaseModel):
    """로그인 요청에서 받는 접근 코드입니다."""

    code: str = Field(min_length=1, max_length=200)


class AdminCodeChange(BaseModel):
    """현재 관리자 코드 검증과 새 코드 확인에 필요한 입력값입니다."""

    current_code: str = Field(min_length=1, max_length=200)
    new_code: str = Field(min_length=8, max_length=200)
    confirmation: str = Field(min_length=8, max_length=200)


def code_hash(code: str) -> str:
    """원본 접근 코드를 저장하지 않도록 SHA-256 해시로 변환합니다."""
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def code_hint(code: str) -> str:
    """목록에서 식별만 가능하도록 코드의 앞부분만 표시합니다."""
    return f"{code[:5]}{'•' * max(4, len(code) - 5)}"


def new_user_code() -> str:
    """사용자에게 한 번 전달할 안전한 임의 접근 코드를 생성합니다."""
    return f"USER-{secrets.token_urlsafe(8).upper()}"


async def fetch_one(database: aiosqlite.Connection, query: str, parameters: tuple = ()):
    """aiosqlite 커서에서 결과 행 하나만 읽어 호출 코드를 단순하게 만듭니다."""
    cursor = await database.execute(query, parameters)
    return await cursor.fetchone()


async def initialize_auth_database() -> None:
    """처음 실행할 때 SQLite 테이블과 기본 접근 코드를 준비합니다."""
    AUTH_DATABASE.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(AUTH_DATABASE) as database:
        await database.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        await database.execute("CREATE TABLE IF NOT EXISTS user_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, code_hash TEXT UNIQUE NOT NULL, hint TEXT NOT NULL, created_at TEXT NOT NULL)")
        existing_admin = await fetch_one(database, "SELECT value FROM settings WHERE key = 'admin_code_hash'")
        if not existing_admin:
            await database.execute("INSERT INTO settings (key, value) VALUES ('admin_code_hash', ?)", (code_hash(INITIAL_ADMIN_CODE),))
        code_count = await fetch_one(database, "SELECT COUNT(*) FROM user_codes")
        if INITIAL_USER_CODE and code_count and code_count[0] == 0:
            await database.execute("INSERT INTO user_codes (code_hash, hint, created_at) VALUES (?, ?, ?)", (code_hash(INITIAL_USER_CODE), code_hint(INITIAL_USER_CODE), datetime.now(timezone.utc).isoformat()))
        await database.commit()


def session_role(token: str | None) -> str | None:
    """Return the signed-in role for a session token, if it is still valid."""
    return SESSIONS.get(token) if token else None


async def require_authenticated(x_marchitect_token: str | None = Header(default=None)) -> str:
    """Allow only requests carrying an active administrator or user session."""
    role = session_role(x_marchitect_token)
    if role not in {"admin", "user"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요합니다.")
    return role


async def require_admin(role: str = Depends(require_authenticated)) -> str:
    """관리자 세션 토큰만 관리자 전용 코드 관리 API에 통과시킵니다."""
    if role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")
    return role


@router.post("/login")
async def login(request: LoginRequest):
    """입력한 접근 코드를 검증하고 브라우저 세션 토큰과 역할을 반환합니다."""
    submitted_hash = code_hash(request.code)
    async with aiosqlite.connect(AUTH_DATABASE) as database:
        admin_row = await fetch_one(database, "SELECT value FROM settings WHERE key = 'admin_code_hash'")
        user_row = await fetch_one(database, "SELECT id FROM user_codes WHERE code_hash = ?", (submitted_hash,))
    role = "admin" if admin_row and secrets.compare_digest(admin_row[0], submitted_hash) else "user" if user_row else None
    if not role:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 접근 코드입니다.")
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = role
    return {"role": role, "token": token}


@router.put("/admin-code")
async def change_admin_code(request: AdminCodeChange, _: str = Depends(require_admin)):
    """현재 코드를 확인한 뒤 일치하는 새 관리자 코드로 교체합니다."""
    if request.new_code != request.confirmation:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="새 관리자 코드와 확인 값이 일치하지 않습니다.")
    async with aiosqlite.connect(AUTH_DATABASE) as database:
        current_row = await fetch_one(database, "SELECT value FROM settings WHERE key = 'admin_code_hash'")
        if not current_row or not secrets.compare_digest(current_row[0], code_hash(request.current_code)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="현재 관리자 코드가 올바르지 않습니다.")
        await database.execute("UPDATE settings SET value = ? WHERE key = 'admin_code_hash'", (code_hash(request.new_code),))
        await database.commit()
    return {"message": "관리자 코드를 변경했습니다."}


@router.get("/user-codes")
async def list_user_codes(_: str = Depends(require_admin)):
    """관리자가 발급한 사용자 코드의 식별 정보와 생성 시각을 반환합니다."""
    async with aiosqlite.connect(AUTH_DATABASE) as database:
        cursor = await database.execute("SELECT id, hint, created_at FROM user_codes ORDER BY id DESC")
        rows = await cursor.fetchall()
    return [{"id": row[0], "hint": row[1], "created_at": row[2]} for row in rows]


@router.post("/user-codes", status_code=status.HTTP_201_CREATED)
async def issue_user_code(_: str = Depends(require_admin)):
    """새 사용자 접근 코드를 생성하고 원본은 이번 응답에서만 반환합니다."""
    access_code = new_user_code()
    created_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(AUTH_DATABASE) as database:
        cursor = await database.execute("INSERT INTO user_codes (code_hash, hint, created_at) VALUES (?, ?, ?)", (code_hash(access_code), code_hint(access_code), created_at))
        await database.commit()
    return {"id": cursor.lastrowid, "code": access_code, "hint": code_hint(access_code), "created_at": created_at}


@router.delete("/user-codes/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_code(code_id: int, _: str = Depends(require_admin)):
    """선택한 사용자 접근 코드를 삭제해 이후 로그인을 막습니다."""
    async with aiosqlite.connect(AUTH_DATABASE) as database:
        cursor = await database.execute("DELETE FROM user_codes WHERE id = ?", (code_id,))
        await database.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자 코드를 찾을 수 없습니다.")
