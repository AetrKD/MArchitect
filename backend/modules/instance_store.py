"""Filesystem storage helpers for one Minecraft server instance per folder."""
import json
import os
import re
import shlex
from pathlib import Path

from fastapi import HTTPException, status

BACKEND_DIR = Path(__file__).resolve().parent.parent
# Docker에서는 /data/instances를 마운트하고, 로컬 실행 시 기존 backend/instance를 사용합니다.
INSTANCE_DIR = Path(os.getenv("MARCHITECT_INSTANCE_DIR", str(BACKEND_DIR / "instance")))
INSTANCE_DIR.mkdir(exist_ok=True)
DEFAULT_JAVA_PATH = os.getenv("MARCHITECT_DEFAULT_JAVA_PATH", "/java/21/bin/java")
DEFAULT_JVM_ARGS = "-Dfile.encoding=UTF-8"


def without_memory_jvm_args(jvm_args: str) -> str:
    """메모리 슬라이더만 메모리를 관리하도록 Xms·Xmx 인수를 제거합니다."""
    return re.sub(r"(?<!\S)-Xm[sx]\S+", "", jvm_args).strip()

def get_instance_path(instance_id: str) -> Path:
    """인스턴스 ID를 검증하고 경로 이탈이 없는 실제 폴더를 반환합니다."""
    instance_path = (INSTANCE_DIR / instance_id).resolve()
    try:
        instance_path.relative_to(INSTANCE_DIR.resolve())
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="인스턴스를 찾을 수 없습니다.") from error

    if not (instance_path / "instance.json").is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="인스턴스를 찾을 수 없습니다.")
    return instance_path


def read_instance(instance_path: Path) -> dict:
    """인스턴스 폴더의 JSON 메타데이터를 읽습니다."""
    return json.loads((instance_path / "instance.json").read_text(encoding="utf-8"))


def write_instance(instance_path: Path, instance: dict) -> None:
    """인스턴스 메타데이터를 UTF-8 JSON 형식으로 저장합니다."""
    (instance_path / "instance.json").write_text(json.dumps(instance, ensure_ascii=False, indent=2), encoding="utf-8")


def write_run_script(instance_path: Path, instance: dict) -> None:
    """저장된 실행 설정으로 리눅스용 run.sh 시작 스크립트를 만듭니다."""
    if instance.get("launch_mode") == "custom":
        command_text = instance.get("custom_command", "").strip()
        if not command_text:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="커스텀 시작 명령어를 입력해 주세요.")
        (instance_path / "run.sh").write_text(f"#!/bin/sh\nset -eu\n\nexec {command_text}\n", encoding="utf-8", newline="\n")
        (instance_path / "run.sh").chmod(0o755)
        return
    java_path = instance.get("java_path", DEFAULT_JAVA_PATH)
    memory_mb = instance.get("memory_mb") or 2048
    extra_jvm_args = without_memory_jvm_args(instance.get("jvm_args", DEFAULT_JVM_ARGS))
    jvm_args = f"-Xms{memory_mb}M -Xmx{memory_mb}M {extra_jvm_args}".strip()
    launch_target = instance.get("launch_target", "server.jar")
    launch_args = instance.get("launch_args", "nogui")
    try:
        if instance.get("launch_kind", "jar") == "argfile":
            # NeoForge's installer creates a versioned unix_args.txt file
            # that starts the actual server launcher. JVM settings are managed
            # by this app, so user_jvm_args.txt is intentionally not included.
            command = [java_path, *shlex.split(jvm_args), f"@{launch_target}", *shlex.split(launch_args)]
        else:
            command = [java_path, *shlex.split(jvm_args), "-jar", launch_target, *shlex.split(launch_args)]
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="JVM 인수 형식이 올바르지 않습니다.") from error

    script = "#!/bin/sh\nset -eu\n\nexec " + " ".join(shlex.quote(argument) for argument in command) + "\n"
    run_script_path = instance_path / "run.sh"
    run_script_path.write_text(script, encoding="utf-8", newline="\n")
    run_script_path.chmod(0o755)


def safe_file_path(instance_path: Path, directory: str, relative_path: str) -> Path:
    """경로 이탈을 막으면서 인스턴스 내부 파일 경로를 안전하게 계산합니다."""
    base_path = (instance_path / directory).resolve()
    target_path = (base_path / relative_path).resolve()
    try:
        target_path.relative_to(base_path)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="허용되지 않는 파일 경로입니다.") from error
    return target_path


def list_directory(directory: Path, relative_path: str = "") -> list[dict]:
    """안전한 인스턴스 하위 폴더의 바로 아래 파일과 폴더만 나열합니다."""
    current_path = (directory / relative_path).resolve()
    try:
        current_path.relative_to(directory.resolve())
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="허용되지 않는 폴더 경로입니다.") from error
    if not current_path.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="폴더를 찾을 수 없습니다.")

    entries = []
    for path in sorted(current_path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        entries.append({
            "name": path.name,
            "path": str(path.relative_to(directory)).replace("\\", "/"),
            "type": "directory" if path.is_dir() else "file",
            "size": None if path.is_dir() else path.stat().st_size,
        })
    return entries
