"""Administrator-managed development hostnames, shared read-only with Vite."""
import json
import ipaddress
from contextlib import closing
import os
from pathlib import Path
import re
import tempfile
import sqlite3
import threading

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from modules.auth import AUTH_DATABASE, require_admin

router = APIRouter(prefix="/settings/domains", tags=["settings"])
SETTINGS_FILE = AUTH_DATABASE.parent / "frontend-settings" / "domains.json"
SETTINGS_LOCK = threading.Lock()


class DomainSettings(BaseModel):
    domains: list[str] = Field(max_length=50)

    @field_validator("domains")
    @classmethod
    def validate_domains(cls, domains):
        normalized = []
        for domain in domains:
            try:
                host = str(ipaddress.ip_address(domain.strip()))
                if host not in normalized:
                    normalized.append(host)
                continue
            except ValueError:
                pass
            try:
                host = domain.strip().rstrip(".").encode("idna").decode("ascii").lower()
            except UnicodeError:
                raise ValueError("유효한 도메인을 입력하세요.")
            labels = host.split(".")
            if len(host) > 253 or len(labels) < 2 or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in labels
            ):
                raise ValueError("도메인만 입력하세요. 주소 앞의 https://, 포트, 경로, 와일드카드는 제외하세요.")
            if host not in normalized:
                normalized.append(host)
        return normalized


@router.get("", dependencies=[Depends(require_admin)])
def read_domains():
    try:
        with closing(sqlite3.connect(AUTH_DATABASE)) as database:
            row = database.execute("SELECT value FROM settings WHERE key = 'allowed_hosts'").fetchone()
        return DomainSettings.model_validate_json(row[0]) if row else DomainSettings(domains=[])
    except (ValueError, sqlite3.Error):
        raise HTTPException(500, "도메인 설정을 불러오지 못했습니다.")


@router.put("", dependencies=[Depends(require_admin)])
def write_domains(settings: DomainSettings):
    with SETTINGS_LOCK:
        try:
            with closing(sqlite3.connect(AUTH_DATABASE)) as database:
                database.execute("INSERT INTO settings (key, value) VALUES ('allowed_hosts', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (settings.model_dump_json(),))
                database.commit()
        except sqlite3.Error:
            raise HTTPException(500, "접속 주소를 DB에 저장하지 못했습니다.")
        try:
            publish_domains(settings)
        except OSError:
            raise HTTPException(500, "DB에는 저장했지만 웹 서버에 적용하지 못했습니다. 다시 저장하거나 백엔드를 재시작해 주세요.")
    return settings


def sync_domain_settings():
    """Recreate the frontend copy from SQLite on every backend startup."""
    with SETTINGS_LOCK:
        publish_domains(read_domains())


def publish_domains(settings):
    # The frontend gets only this derived file, never access to the auth DB.
    temporary = None
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=SETTINGS_FILE.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(settings.model_dump(), output)
        # Only hostnames are shared. Allow the separate frontend user to read.
        temporary.chmod(0o644)
        os.replace(temporary, SETTINGS_FILE)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return settings
