"""Persistent weekly instance rules. Weekdays are Monday=0 through Sunday=6."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator, model_validator

from modules.auth import require_admin
from modules.instance_store import INSTANCE_DIR, atomic_json, get_instance_path, instance_lock

router = APIRouter(prefix="/instances", tags=["instance-rules"])
logger = logging.getLogger(__name__)


class Rule(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex, pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    kind: Literal["start", "stop", "restriction"]
    enabled: bool = True
    days: list[int] = Field(min_length=1, max_length=7)
    time: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    end_time: str | None = Field(default=None, pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")

    @field_validator("days")
    @classmethod
    def validate_days(cls, days):
        if any(day < 0 or day > 6 for day in days) or len(set(days)) != len(days):
            raise ValueError("요일은 중복 없이 월요일(0)부터 일요일(6)까지 선택하세요.")
        return sorted(days)

    @model_validator(mode="after")
    def validate_window(self):
        if self.kind == "restriction" and (not self.end_time or self.end_time == self.time):
            raise ValueError("제한 시작과 종료 시각을 서로 다르게 지정하세요.")
        return self


class Rules(BaseModel):
    timezone: str = "Asia/Seoul"
    rules: list[Rule] = Field(default_factory=list, max_length=100)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("유효한 시간대를 선택하세요.") from error
        return value

    @model_validator(mode="after")
    def validate_ids(self):
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError("규칙 ID가 중복되었습니다.")
        return self


def load_rules(path):
    import json
    file = path / "rules.json"
    return Rules.model_validate_json(file.read_text(encoding="utf-8")) if file.exists() else Rules()


def restricted(config: Rules, now: datetime) -> bool:
    local = now.astimezone(ZoneInfo(config.timezone))
    clock = local.strftime("%H:%M")
    for rule in config.rules:
        if not rule.enabled or rule.kind != "restriction":
            continue
        if rule.time < rule.end_time:
            if local.weekday() in rule.days and rule.time <= clock < rule.end_time:
                return True
        elif ((local.weekday() in rule.days and clock >= rule.time)
              or ((local.weekday() - 1) % 7 in rule.days and clock < rule.end_time)):
            return True
    return False


def is_start_restricted(path, now=None):
    return restricted(load_rules(path), now or datetime.now(timezone.utc))


@router.get("/{instance_id}/rules")
async def get_rules(instance_id: str):
    return load_rules(get_instance_path(instance_id)).model_dump()


@router.put("/{instance_id}/rules", dependencies=[Depends(require_admin)])
async def put_rules(instance_id: str, config: Rules):
    path = get_instance_path(instance_id)
    with instance_lock(path):
        atomic_json(path / "rules.json", config.model_dump())
    return config.model_dump()


def run_pending(now=None):
    import json
    from modules.server_process import start, stop
    now = now or datetime.now(timezone.utc)
    for path in INSTANCE_DIR.iterdir():
        if not (path / "instance.json").is_file():
            continue
        try:
            with instance_lock(path):
                config = load_rules(path)
                local = now.astimezone(ZoneInfo(config.timezone))
                state_file = path / "rule-state.json"
                state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
                due = [rule for rule in config.rules if rule.enabled and rule.kind != "restriction"
                       and local.weekday() in rule.days and rule.time == local.strftime("%H:%M")]
                # A stop always wins over a simultaneous start.
                if any(rule.kind == "stop" for rule in due):
                    due = [rule for rule in due if rule.kind == "stop"]
                for rule in due:
                    # Local date/time deliberately deduplicates the repeated DST hour.
                    occurrence = local.strftime("%Y-%m-%dT%H:%M")
                    if state.get(rule.id, {}).get("occurrence") == occurrence:
                        continue
                    state[rule.id] = {"occurrence": occurrence, "status": "claimed"}
                    atomic_json(state_file, state)
                    try:
                        (start if rule.kind == "start" else stop)(path)
                        state[rule.id]["status"] = "completed"
                    except Exception as error:
                        state[rule.id].update(status="failed", error=str(getattr(error, "detail", error)))
                        logger.exception("Instance rule failed: %s/%s", path.name, rule.id)
                    atomic_json(state_file, state)
        except Exception:
            logger.exception("Cannot evaluate instance rules: %s", path)


async def scheduler():
    while True:
        await asyncio.to_thread(run_pending)
        await asyncio.sleep(5)
