"""Small in-process task registry for long running downloads.

Tasks survive browser navigation. They are intentionally not durable across a
backend restart; a queue such as Redis can replace this module when deployed.
"""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/tasks", tags=["tasks"])
TASKS: dict[str, dict] = {}


def now() -> str:
    """작업 기록에 사용할 현재 UTC 시각을 문자열로 반환합니다."""
    return datetime.now(timezone.utc).isoformat()


def start_task(title: str, work) -> dict:
    """코루틴을 백그라운드 작업으로 등록하고 화면용 작업 정보를 반환합니다."""
    task_id = uuid4().hex
    record = {"id": task_id, "title": title, "status": "queued", "progress": 0, "created_at": now(), "updated_at": now()}
    TASKS[task_id] = record

    async def runner():
        """대기 중인 작업을 실행하고 완료 또는 실패 상태를 기록합니다."""
        record.update(status="running", progress=5, updated_at=now())
        try:
            result = await work(record)
            record.update(status="completed", progress=100, result=result, updated_at=now())
        except Exception as error:
            detail = getattr(error, "detail", None)
            record.update(status="failed", error=str(detail or error), updated_at=now())

    asyncio.create_task(runner())
    return record


def update_progress(record: dict, progress: int, message: str | None = None, indeterminate: bool | None = None) -> None:
    """진행률 범위를 제한해 저장하고 필요하면 현재 단계를 함께 기록합니다."""
    record.update(progress=max(0, min(progress, 99)), updated_at=now())
    if message:
        record["message"] = message[:300]
    if indeterminate is not None:
        record["indeterminate"] = indeterminate


@router.get("")
async def list_tasks():
    """진행 화면에 표시할 최신 백그라운드 작업 30개를 반환합니다."""
    return sorted(TASKS.values(), key=lambda task: task["created_at"], reverse=True)[:30]


@router.get("/{task_id}")
async def get_task(task_id: str):
    """작업 ID에 해당하는 기록을 반환하고 없으면 404 오류를 냅니다."""
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return TASKS[task_id]
