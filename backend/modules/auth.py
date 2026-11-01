"""접근 코드 로그인과 관리자 전용 코드 관리를 제공하는 API입니다."""
import hashlib
import asyncio
import os
import secrets
import time
from collections import deque
from functools import wraps
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
from fastapi import APIRouter, Depends, Header, Request, HTTPException, status
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/auth", tags=["auth"])
AUTH_DATABASE = Path(os.getenv("MARCHITECT_AUTH_DB", "/data/marchitect.sqlite3"))
INITIAL_ADMIN_CODE = os.getenv("MARCHITECT_INITIAL_ADMIN_CODE", "ADMIN")
INITIAL_USER_CODE = os.getenv("MARCHITECT_INITIAL_USER_CODE", "")
SESSIONS: dict[str, dict] = {}
LOGIN_ATTEMPTS: dict[str, deque] = {}
SESSION_SECONDS = 12 * 60 * 60
AUTH_LOCK = asyncio.Lock()


def serialized_auth(function):
    @wraps(function)
    async def guarded(*args, **kwargs):
        async with AUTH_LOCK:
            return await function(*args, **kwargs)
    return guarded


def secure_hash(code: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(code.strip().encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return "scrypt$16384$8$1$" + salt + "$" + digest


def verify_code(code: str, stored: str) -> bool:
    if not stored.startswith("scrypt$"):
        return secrets.compare_digest(code_hash(code), stored)
    _, n, r, p, salt, expected = stored.split("$")
    actual = hashlib.scrypt(code.strip().encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p)).hex()
    return secrets.compare_digest(actual, expected)


def revoke_sessions(role=None, code_id=None):
    for token, record in list(SESSIONS.items()):
        if (role is None or record["role"] == role) and (code_id is None or record.get("code_id") == code_id):
            SESSIONS.pop(token, None)



class LoginRequest(BaseModel):
    """로그인 요청에서 받는 접근 코드입니다."""

    code: str = Field(min_length=1, max_length=200)


class AdminCodeChange(BaseModel):
    """현재 관리자 코드 검증과 새 코드 확인에 필요한 입력값입니다."""

    current_code: str = Field(min_length=1, max_length=200)
    new_code: str = Field(min_length=8, max_length=200)
    confirmation: str = Field(min_length=8, max_length=200)

    @field_validator("new_code", "confirmation")
    @classmethod
    def validate_code(cls, value):
        value = value.strip()
        if len(value) < 8:
            raise ValueError("공백을 제외한 접근 코드는 8자 이상이어야 합니다.")
        return value


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
            await database.execute("INSERT INTO settings (key, value) VALUES ('admin_code_hash', ?)", (secure_hash(INITIAL_ADMIN_CODE),))
        code_count = await fetch_one(database, "SELECT COUNT(*) FROM user_codes")
        if INITIAL_USER_CODE and code_count and code_count[0] == 0:
            await database.execute("INSERT INTO user_codes (code_hash, hint, created_at) VALUES (?, ?, ?)", (secure_hash(INITIAL_USER_CODE), code_hint(INITIAL_USER_CODE), datetime.now(timezone.utc).isoformat()))
        await database.commit()


def session_role(token: str | None) -> str | None:
    """Return the signed-in role for a session token, if it is still valid."""
    record = SESSIONS.get(token) if token else None
    if not record:
        return None
    if record["expires"] <= time.monotonic():
        SESSIONS.pop(token, None)
        return None
    return record["role"]


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
@serialized_auth
async def login(request: LoginRequest, http_request: Request):
    address = http_request.client.host if http_request.client else "unknown"
    now = time.monotonic()
    for key in list(LOGIN_ATTEMPTS):
        if not LOGIN_ATTEMPTS[key] or LOGIN_ATTEMPTS[key][-1] < now - 300:
            LOGIN_ATTEMPTS.pop(key, None)
    attempts = LOGIN_ATTEMPTS.setdefault(address, deque())
    while attempts and attempts[0] < now - 300:
        attempts.popleft()
    if len(attempts) >= 10 or sum(map(len, LOGIN_ATTEMPTS.values())) >= 100:
        raise HTTPException(429, "로그인 시도가 너무 많습니다. 5분 후 다시 시도하세요.")
    attempts.append(now)
    role = None
    code_id = None
    async with aiosqlite.connect(AUTH_DATABASE) as database:
        admin = await fetch_one(database, "SELECT value FROM settings WHERE key = 'admin_code_hash'")
        if admin and await asyncio.to_thread(verify_code, request.code, admin[0]):
            role = "admin"
            if not admin[0].startswith("scrypt$"):
                hashed = await asyncio.to_thread(secure_hash, request.code)
                await database.execute("UPDATE settings SET value = ? WHERE key = 'admin_code_hash'", (hashed,))
        else:
            cursor = await database.execute("SELECT id, code_hash FROM user_codes")
            for row in await cursor.fetchall():
                if await asyncio.to_thread(verify_code, request.code, row[1]):
                    role, code_id = "user", row[0]
                    if not row[1].startswith("scrypt$"):
                        hashed = await asyncio.to_thread(secure_hash, request.code)
                        await database.execute("UPDATE user_codes SET code_hash = ? WHERE id = ?", (hashed, code_id))
                    break
        await database.commit()
    if not role:
        raise HTTPException(401, "유효하지 않은 접근 코드입니다.")
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"role": role, "code_id": code_id, "expires": now + SESSION_SECONDS}
    return {"role": role, "token": token}


@router.post("/logout")
async def logout(x_marchitect_token: str | None = Header(default=None)):
    SESSIONS.pop(x_marchitect_token, None)
    return {"message": "로그아웃했습니다."}


@router.put("/admin-code")
@serialized_auth
async def change_admin_code(request: AdminCodeChange, _: str = Depends(require_admin)):
    """현재 코드를 확인한 뒤 일치하는 새 관리자 코드로 교체합니다."""
    if request.new_code != request.confirmation:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="새 관리자 코드와 확인 값이 일치하지 않습니다.")
    async with aiosqlite.connect(AUTH_DATABASE) as database:
        current_row = await fetch_one(database, "SELECT value FROM settings WHERE key = 'admin_code_hash'")
        if not current_row or not await asyncio.to_thread(verify_code, request.current_code, current_row[0]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="현재 관리자 코드가 올바르지 않습니다.")
        await database.execute("UPDATE settings SET value = ? WHERE key = 'admin_code_hash'", (await asyncio.to_thread(secure_hash, request.new_code),))
        await database.commit()
    revoke_sessions(role="admin")
    return {"message": "관리자 코드를 변경했습니다. 다시 로그인하세요."}


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
        cursor = await database.execute("INSERT INTO user_codes (code_hash, hint, created_at) VALUES (?, ?, ?)", (await asyncio.to_thread(secure_hash, access_code), code_hint(access_code), created_at))
        await database.commit()
    return {"id": cursor.lastrowid, "code": access_code, "hint": code_hint(access_code), "created_at": created_at}


@router.delete("/user-codes/{code_id}", status_code=status.HTTP_204_NO_CONTENT)
@serialized_auth
async def delete_user_code(code_id: int, _: str = Depends(require_admin)):
    """선택한 사용자 접근 코드를 삭제해 이후 로그인을 막습니다."""
    async with aiosqlite.connect(AUTH_DATABASE) as database:
        cursor = await database.execute("DELETE FROM user_codes WHERE id = ?", (code_id,))
        await database.commit()
    revoke_sessions(role="user", code_id=code_id)
    if cursor.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="사용자 코드를 찾을 수 없습니다.")


if __name__ == "__main__":
    # Initialize as the runtime user before importing the rest of the app.
    import sys

    print(f"[marchitect] initializing SQLite database at {AUTH_DATABASE.resolve()}", flush=True)
    try:
        asyncio.run(initialize_auth_database())
    except Exception as error:
        print(f"[marchitect] error: SQLite initialization failed at {AUTH_DATABASE.resolve()}: {error}", file=sys.stderr)
        sys.exit(1)
    print(f"[marchitect] SQLite database ready at {AUTH_DATABASE.resolve()}", flush=True)
