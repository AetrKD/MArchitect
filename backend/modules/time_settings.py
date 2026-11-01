"""Service timezone preferences and authoritative server clock."""
from contextlib import closing
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import threading
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from modules.auth import AUTH_DATABASE, require_admin, require_authenticated

router = APIRouter(prefix="/settings/time", tags=["settings"])
TIME_LOCK = threading.RLock()
SERVICE_TIMEZONE = "system"


class TimeSettings(BaseModel):
    timezone: str = Field(default="system", max_length=100)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        if value != "system":
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError) as error:
                raise ValueError("유효한 IANA 시간대를 입력하세요. 예: Asia/Seoul") from error
        return value


def sync_time_settings():
    global SERVICE_TIMEZONE
    with TIME_LOCK, closing(sqlite3.connect(AUTH_DATABASE)) as database:
        row = database.execute("SELECT value FROM settings WHERE key = 'service_timezone'").fetchone()
        SERVICE_TIMEZONE = TimeSettings(timezone=row[0] if row else "system").timezone


def system_local_time(now):
    configured = os.getenv("TZ", "").lstrip(":")
    if configured:
        try:
            return now.astimezone(ZoneInfo(configured))
        except (ZoneInfoNotFoundError, ValueError):
            pass
    localtime = Path("/etc/localtime")
    if localtime.is_file():
        with localtime.open("rb") as source:
            return now.astimezone(ZoneInfo.from_file(source))
    return now.astimezone()


def service_local_time(now):
    zone = SERVICE_TIMEZONE
    return system_local_time(now) if zone == "system" else now.astimezone(ZoneInfo(zone))


def clock_payload():
    current = service_local_time(datetime.now(timezone.utc))
    return {"timezone": SERVICE_TIMEZONE, "current_time": current.isoformat(),
            "timezone_label": current.tzname(), "utc_offset_seconds": int(current.utcoffset().total_seconds())}


@router.get("", dependencies=[Depends(require_authenticated)])
def get_clock():
    return clock_payload()


@router.put("", dependencies=[Depends(require_admin)])
def set_timezone(settings: TimeSettings):
    global SERVICE_TIMEZONE
    with TIME_LOCK:
        try:
            with closing(sqlite3.connect(AUTH_DATABASE)) as database:
                database.execute("INSERT INTO settings (key, value) VALUES ('service_timezone', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (settings.timezone,))
                database.commit()
        except sqlite3.Error as error:
            raise HTTPException(500, "시간대를 저장하지 못했습니다.") from error
        SERVICE_TIMEZONE = settings.timezone
        return clock_payload()
