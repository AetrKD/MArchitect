"""Persistent download history with explicit interruption recovery on restart."""
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
import json
import shutil
import threading
from modules.auth import AUTH_DATABASE
from modules.instance_store import INSTANCE_DIR, atomic_json
from modules.java_admin_paths import JAVA_INSTALL_DIR

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/tasks", tags=["tasks"])
TASKS: dict[str, dict] = {}
RUNNERS: set[asyncio.Task] = set()
TASK_FILE = AUTH_DATABASE.parent / "tasks.json"
TASK_LOCK = threading.RLock()


class TaskRecord(dict):
    def update(self, *args, **kwargs):
        with TASK_LOCK:
            super().update(*args, **kwargs)
            persist_tasks()


def persist_tasks():
    with TASK_LOCK:
        atomic_json(TASK_FILE, {"tasks": list(TASKS.values())})


def restore_tasks():
    TASKS.clear()
    if TASK_FILE.exists():
        for saved in json.loads(TASK_FILE.read_text(encoding="utf-8")).get("tasks", []):
            record = TaskRecord(saved)
            TASKS[record["id"]] = record
            if record["status"] in {"queued", "running"}:
                record.update(status="failed", error="백엔드 재시작으로 작업이 중단되었습니다. 다시 시도하세요.", updated_at=now())
    # Only app-owned uncommitted staging folders are removed; completed instances remain untouched.
    for base in (INSTANCE_DIR, JAVA_INSTALL_DIR):
        for path in base.glob(".install-*"):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
    persist_tasks()


async def shutdown_tasks():
    for task in list(RUNNERS):
        task.cancel()
    await asyncio.gather(*RUNNERS, return_exceptions=True)



def now() -> str:
    """작업 기록에 사용할 현재 UTC 시각을 문자열로 반환합니다."""
    return datetime.now(timezone.utc).isoformat()


def start_task(title: str, work) -> dict:
    """코루틴을 백그라운드 작업으로 등록하고 화면용 작업 정보를 반환합니다."""
    task_id = uuid4().hex
    record = TaskRecord({"id": task_id, "title": title, "status": "queued", "progress": 0, "created_at": now(), "updated_at": now()})
    TASKS[task_id] = record
    persist_tasks()

    async def runner():
        """대기 중인 작업을 실행하고 완료 또는 실패 상태를 기록합니다."""
        record.update(status="running", progress=5, updated_at=now())
        try:
            result = await work(record)
            record.update(status="completed", progress=100, result=result, updated_at=now())
        except asyncio.CancelledError:
            record.update(status="failed", error="백엔드 종료로 작업이 중단되었습니다. 다시 시도하세요.", updated_at=now())
            raise
        except Exception as error:
            detail = getattr(error, "detail", None)
            record.update(status="failed", error=str(detail or error), updated_at=now())

    task = asyncio.create_task(runner())
    RUNNERS.add(task)
    task.add_done_callback(RUNNERS.discard)
    return record


def update_progress(record: dict, progress: int, message: str | None = None, indeterminate: bool | None = None) -> None:
    """진행률 범위를 제한해 저장하고 필요하면 현재 단계를 함께 기록합니다."""
    record.update(progress=max(0, min(progress, 99)), updated_at=now())
    if message:
        record["message"] = message[:300]
    if indeterminate is not None:
        record["indeterminate"] = indeterminate
    persist_tasks()


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
