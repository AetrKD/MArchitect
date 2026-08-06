"""Managed Minecraft processes with persistent logs and live console buffers."""
import subprocess
import threading
import shutil
import os
import time
from collections import deque
from pathlib import Path

from modules.instance_store import get_instance_path, read_instance, write_instance, write_run_script

PROCESSES: dict[str, subprocess.Popen] = {}
LINES: dict[str, deque[str]] = {}
PROCESS_SAMPLES: dict[str, tuple[float, int]] = {}


def _collect_output(instance_path: Path, instance_id: str, process: subprocess.Popen, log_path: Path) -> None:
    """브라우저 연결 여부와 무관하게 서버 출력을 로그 파일에 계속 저장합니다."""
    buffer = LINES.setdefault(instance_id, deque(maxlen=500))
    with log_path.open("a", encoding="utf-8") as log_file:
        for line in iter(process.stdout.readline, ""):
            log_file.write(line); log_file.flush(); buffer.append(line.rstrip("\n"))
            if "Done (" in line:
                instance = read_instance(instance_path); instance["status"] = "running"; write_instance(instance_path, instance)
    instance = read_instance(instance_path)
    # A newer process may have been started while this output reader was ending.
    if instance.get("process_pid") == process.pid:
        instance["status"] = "stopped"
        instance.pop("process_pid", None)
        write_instance(instance_path, instance)


def _process_uses_instance_directory(process_id: int, instance_path: Path) -> bool:
    """리눅스 프로세스의 작업 경로가 이 인스턴스 폴더인지 확인합니다."""
    try:
        return Path(f"/proc/{process_id}/cwd").resolve() == instance_path.resolve()
    except (FileNotFoundError, OSError):
        return False


def find_process_id(instance_id: str) -> int | None:
    """백엔드 재시작 뒤에도 살아 있는 인스턴스 프로세스를 찾아냅니다."""
    managed_process = PROCESSES.get(instance_id)
    if managed_process and managed_process.poll() is None:
        return managed_process.pid

    instance_path = get_instance_path(instance_id)
    instance = read_instance(instance_path)
    saved_process_id = instance.get("process_pid")
    if isinstance(saved_process_id, int) and _process_uses_instance_directory(saved_process_id, instance_path):
        return saved_process_id

    # Uvicorn reload clears this module's memory, but the Java child can keep
    # running. Its working directory uniquely identifies the instance folder.
    for process_path in Path("/proc").iterdir():
        if process_path.name.isdigit() and _process_uses_instance_directory(int(process_path.name), instance_path):
            process_id = int(process_path.name)
            instance["process_pid"] = process_id
            write_instance(instance_path, instance)
            return process_id
    return None


def start(instance_path: Path) -> dict:
    """인스턴스의 run.sh를 실행하고 표준 출력을 계속 수집하도록 연결합니다."""
    instance = read_instance(instance_path)
    if instance["id"] in PROCESSES and PROCESSES[instance["id"]].poll() is None:
        return instance
    logs = instance_path / "logs"
    # Each new server start begins with a clean log history as requested.
    if logs.exists():
        for path in logs.iterdir():
            if path.is_dir(): shutil.rmtree(path)
            else: path.unlink()
    logs.mkdir(exist_ok=True)
    # The browser console reads this separate in-memory tail, so reset it
    # together with the on-disk logs for a genuinely clean new start.
    LINES[instance["id"]] = deque(maxlen=500)
    # Always regenerate from the saved execution settings so an updated
    # launcher format is reflected on the next server start.
    write_run_script(instance_path, instance)
    process = subprocess.Popen(["/bin/sh", "./run.sh"], cwd=instance_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    PROCESSES[instance["id"]] = process
    threading.Thread(target=_collect_output, args=(instance_path, instance["id"], process, logs / "latest.log"), daemon=True).start()
    instance["status"] = "starting"
    instance["process_pid"] = process.pid
    write_instance(instance_path, instance)
    return instance


def recent_lines(instance_id: str) -> list[str]:
    """새 콘솔 연결에 보낼 최근 실시간 로그 줄을 반환합니다."""
    return list(LINES.get(instance_id, ()))


def process_metrics(instance_id: str) -> dict | None:
    """백엔드 재시작 후에도 실행 중인 서버의 CPU와 메모리를 측정합니다."""
    process_id = find_process_id(instance_id)
    if process_id is None:
        PROCESS_SAMPLES.pop(instance_id, None)
        return None
    try:
        stat_values = Path(f"/proc/{process_id}/stat").read_text().split()
        cpu_ticks = int(stat_values[13]) + int(stat_values[14])
        rss_kb = next(int(line.split()[1]) for line in Path(f"/proc/{process_id}/status").read_text().splitlines() if line.startswith("VmRSS:"))
    except (FileNotFoundError, IndexError, StopIteration, ValueError):
        return None
    now = time.monotonic()
    previous = PROCESS_SAMPLES.get(instance_id)
    PROCESS_SAMPLES[instance_id] = (now, cpu_ticks)
    if previous:
        elapsed = max(now - previous[0], 0.001)
        # Convert process core usage into a percentage of all visible CPUs so
        # the dashboard remains within a familiar 0–100% scale.
        cpu_percent = round(((cpu_ticks - previous[1]) / os.sysconf("SC_CLK_TCK")) / elapsed * 100 / max(os.cpu_count() or 1, 1), 1)
    else:
        cpu_percent = 0.0
    return {"cpu_percent": max(0.0, min(cpu_percent, 100.0)), "memory_used": rss_kb * 1024}


def send_command(instance_id: str, command: str) -> bool:
    """실행 중인 서버의 표준 입력으로 콘솔 명령 한 줄을 보냅니다."""
    process = PROCESSES.get(instance_id)
    if not process or process.poll() is not None or not process.stdin:
        return False
    process.stdin.write(command + "\n"); process.stdin.flush(); return True


def stop(instance_path: Path) -> dict:
    """관리 중인 마인크래프트 서버에 정상 종료 명령을 요청합니다."""
    instance = read_instance(instance_path); process = PROCESSES.get(instance["id"])
    if process and process.poll() is None:
        send_command(instance["id"], "stop")
    instance["status"] = "stopping"; write_instance(instance_path, instance); return instance


def force_stop(instance_path: Path) -> dict:
    """정상 종료가 불가능한 서버 프로세스를 즉시 강제 종료합니다."""
    instance = read_instance(instance_path); process = PROCESSES.get(instance["id"])
    if process and process.poll() is None:
        process.kill()
    elif process_id := find_process_id(instance["id"]):
        os.kill(process_id, 9)
    instance["status"] = "stopped"
    instance.pop("process_pid", None)
    write_instance(instance_path, instance)
    return instance
