"""Managed Minecraft processes with persistent logs and live console buffers."""
import subprocess
import os
import time
import sys
import signal
from fastapi import HTTPException
from pathlib import Path
from functools import wraps

from modules.instance_store import get_instance_path, read_instance, write_instance, write_run_script, instance_lock, MAINTENANCE

PROCESSES: dict[str, subprocess.Popen] = {}
PROCESS_SAMPLES: dict[str, tuple[float, int]] = {}


def locked_status(function):
    @wraps(function)
    def guarded(instance_path):
        with instance_lock(instance_path):
            return function(instance_path)
    return guarded


def _is_instance_server_process(process_id: int, instance_path: Path) -> bool:
    """리눅스 프로세스의 작업 경로가 이 인스턴스 폴더인지 확인합니다."""
    try:
        if Path(f"/proc/{process_id}/cwd").resolve() != instance_path.resolve():
            return False
        command = Path(f"/proc/{process_id}/cmdline").read_bytes().split(b"\0")
        executable = Path(command[0].decode("utf-8", errors="ignore")).name.lower() if command else ""
        return executable.startswith("java")
    except (FileNotFoundError, OSError, UnicodeError):
        return False


def find_process_id(instance_id: str) -> int | None:
    """백엔드 재시작 뒤에도 살아 있는 인스턴스 프로세스를 찾아냅니다."""
    instance_path = get_instance_path(instance_id)
    managed_process = PROCESSES.get(instance_id)
    if managed_process and managed_process.poll() is None:
        # `run.sh` normally execs Java. If a launcher leaves a shell behind,
        # do not mistake that shell for a still-running Minecraft server.
        if _is_instance_server_process(managed_process.pid, instance_path):
            return managed_process.pid

    instance = read_instance(instance_path)
    saved_process_id = instance.get("process_pid")
    if isinstance(saved_process_id, int) and _is_instance_server_process(saved_process_id, instance_path):
        return saved_process_id

    # Uvicorn reload clears this module's memory, but the Java child can keep
    # running. Its working directory uniquely identifies the instance folder.
    for process_path in Path("/proc").iterdir():
        if process_path.name.isdigit() and _is_instance_server_process(int(process_path.name), instance_path):
            process_id = int(process_path.name)
            instance["process_pid"] = process_id
            write_instance(instance_path, instance)
            return process_id
    return None


@locked_status
def synchronize_status(instance_path: Path) -> dict:
    """Synchronize saved state with the actual Java server process."""
    instance = read_instance(instance_path)
    process_id = find_process_id(instance["id"])
    if process_id is None:
        supervisor = instance.get("supervisor_pid")
        if supervisor and _is_supervisor(supervisor, instance_path):
            return instance
        if instance.get("status") != "stopped" or "process_pid" in instance:
            instance["status"] = "stopped"
            instance.pop("process_pid", None)
            write_instance(instance_path, instance)
        return instance
    if instance.get("status") == "starting":
        _, lines = console_snapshot(instance["id"])
        if (instance_path / ".server-ready").exists() or any("Done (" in line for line in lines):
            instance["status"] = "running"
            write_instance(instance_path, instance)
    if instance.get("status") not in {"starting", "stopping", "running"}:
        instance["status"] = "running"
        instance["process_pid"] = process_id
        write_instance(instance_path, instance)
    return instance


def start(instance_path: Path) -> dict:
    with instance_lock(instance_path):
        if str(instance_path.resolve()) in MAINTENANCE:
            raise HTTPException(409, "파일 작업이 진행 중입니다.")
        instance = read_instance(instance_path)
        if find_process_id(instance["id"]) is not None:
            return synchronize_status(instance_path)
        previous = PROCESSES.get(instance["id"])
        if previous and previous.poll() is None:
            return instance
        saved_supervisor = instance.get("supervisor_pid")
        if saved_supervisor and _is_supervisor(saved_supervisor, instance_path):
            return instance
        logs = instance_path / "logs"
        logs.mkdir(exist_ok=True)
        latest = logs / "latest.log"
        if latest.exists():
            latest.replace(logs / f"server-{time.time_ns()}.log")
        # Keep the newest 20 archived logs instead of deleting diagnostic history.
        for old in sorted(logs.glob("server-*.log"), reverse=True)[20:]:
            old.unlink()
        (instance_path / ".server-ready").unlink(missing_ok=True)
        fifo = instance_path / ".console-input"
        fifo.unlink(missing_ok=True)
        os.mkfifo(fifo, 0o600)
        write_run_script(instance_path, instance)
        supervisor = Path(__file__).with_name("process_supervisor.py")
        with latest.open("a", encoding="utf-8") as output:
            process = subprocess.Popen([sys.executable, str(supervisor), str(fifo)], cwd=instance_path,
                                       stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        PROCESSES[instance["id"]] = process
        instance.update(status="starting", supervisor_pid=process.pid)
        instance.pop("process_pid", None)
        write_instance(instance_path, instance)
        return instance


def _is_supervisor(pid: int, instance_path: Path) -> bool:
    try:
        return (Path(f"/proc/{pid}/cwd").resolve() == instance_path.resolve()
                and b"process_supervisor.py" in Path(f"/proc/{pid}/cmdline").read_bytes())
    except OSError:
        return False


def recent_lines(instance_id: str) -> list[str]:
    """새 콘솔 연결에 보낼 최근 실시간 로그 줄을 반환합니다."""
    return console_snapshot(instance_id)[1]


def console_snapshot(instance_id: str) -> tuple[int, list[str]]:
    path = get_instance_path(instance_id) / "logs" / "latest.log"
    if not path.exists():
        return 0, []
    # Bound memory and I/O regardless of how large the log has grown.
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        stream.seek(max(0, size - 256 * 1024))
        data = stream.read()
    lines = data.decode("utf-8", errors="replace").splitlines()[-500:]
    return (path.stat().st_ino << 64) + size, lines


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
    if not command.strip() or "\n" in command or "\r" in command or len(command.encode()) > 4000:
        return False
    path = get_instance_path(instance_id)
    if find_process_id(instance_id) is None:
        return False
    try:
        fd = os.open(path / ".console-input", os.O_WRONLY | os.O_NONBLOCK)
        try:
            os.write(fd, (command + "\n").encode("utf-8"))
        finally:
            os.close(fd)
        return True
    except OSError:
        return False


def stop(instance_path: Path) -> dict:
    with instance_lock(instance_path):
        instance = synchronize_status(instance_path)
        if instance["status"] == "stopped":
            return instance
        if not send_command(instance["id"], "stop"):
            raise HTTPException(409, "정상 종료 명령을 전달하지 못했습니다. 기존 방식으로 시작한 서버는 강제 종료 후 다시 시작하세요.")
        instance["status"] = "stopping"
        write_instance(instance_path, instance)
        return instance


def force_stop(instance_path: Path) -> dict:
    with instance_lock(instance_path):
        instance = read_instance(instance_path)
        supervisor = instance.get("supervisor_pid")
        if supervisor and _is_supervisor(supervisor, instance_path):
            os.killpg(supervisor, signal.SIGKILL)
        elif process_id := find_process_id(instance["id"]):
            os.kill(process_id, signal.SIGKILL)
        process = PROCESSES.pop(instance["id"], None)
        if process:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                raise HTTPException(409, "프로세스 종료를 기다리고 있습니다.")
        instance.update(status="stopped")
        instance.pop("process_pid", None)
        instance.pop("supervisor_pid", None)
        write_instance(instance_path, instance)
        return instance
