"""Instance creation, configuration, file access and lifecycle API endpoints."""
import asyncio
import io
import mimetypes
import os
import re
import selectors
import shutil
import subprocess
import struct
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from modules.instance_store import (
    DEFAULT_JAVA_PATH,
    DEFAULT_JVM_ARGS,
    INSTANCE_DIR,
    get_instance_path,
    list_directory,
    read_instance,
    safe_file_path,
    without_memory_jvm_args,
    write_instance,
    write_run_script,
)
from modules.downloads import download_remote_file
from modules.server_catalog import fabric_download, neoforge_download_url, paper_download_url
from modules.task_store import start_task, update_progress
from modules.server_process import console_snapshot, force_stop, process_metrics, send_command, start as start_process, stop as stop_process, synchronize_status
from modules.auth import require_admin, session_role

router = APIRouter(prefix="/instances", tags=["instances"])
MAX_JAR_SIZE_BYTES = 200 * 1024 * 1024
MAX_TEXT_VIEW_BYTES = 2 * 1024 * 1024
MAX_SERVER_ICON_BYTES = 2 * 1024 * 1024
TEXT_FILE_SUFFIXES = {".txt", ".log", ".json", ".properties", ".yml", ".yaml", ".toml", ".cfg", ".conf", ".ini", ".sh", ".bat", ".md", ".csv", ".xml", ".html", ".js", ".py"}


class TextUpdate(BaseModel):
    content: str


class NameUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class RuntimeUpdate(BaseModel):
    jvm_args: str = Field(max_length=2000)
    java_path: str | None = Field(default=None, max_length=500)
    memory_mb: int | None = Field(default=None, ge=256)
    launch_mode: Literal["basic", "custom"] = "basic"
    custom_command: str = Field(default="", max_length=4000)
    launch_target: str = Field(min_length=1, max_length=1000)


class NameListUpdate(BaseModel):
    names: list[str] = Field(max_length=500)


StorageArea = Literal["world", "mods", "plugins", "config", "logs"]


def storage_root(instance_path: Path, area: StorageArea) -> Path:
    """파일 탐색기에 허용된 인스턴스 하위 폴더 하나를 반환합니다."""
    return instance_path / area


def is_text_file(path: Path) -> bool:
    """바이너리를 열지 않도록 일반적인 텍스트 파일인지 판별합니다."""
    mime_type, _ = mimetypes.guess_type(path.name)
    return path.suffix.lower() in TEXT_FILE_SUFFIXES or bool(mime_type and mime_type.startswith("text/"))


def resolve_instance_file(instance_path: Path, relative_path: str) -> Path:
    """인스턴스 폴더 밖으로 벗어나지 않게 기존 실행 파일 경로를 확인합니다."""
    candidate = (instance_path / relative_path).resolve()
    try:
        candidate.relative_to(instance_path.resolve())
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="실행 파일은 인스턴스 폴더 안에 있어야 합니다.") from error
    if not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="실행 파일 경로에서 파일을 찾을 수 없습니다.")
    return candidate


def configure_neoforge_launch(instance_path: Path, instance: dict) -> None:
    """Read NeoForge's generated run.sh and retain its real server argfile."""
    generated_script = instance_path / "run.sh"
    try:
        script = generated_script.read_text(encoding="utf-8")
    except OSError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="NeoForge installation is incomplete: generated run.sh was not found.",
        ) from error

    matches = re.findall(r"@(?:'([^']*unix_args\.txt)'|\"([^\"]*unix_args\.txt)\"|([^\s]+unix_args\.txt))", script)
    for match in matches:
        target = next((value for value in match if value), "")
        candidate = (instance_path / target).resolve()
        try:
            candidate.relative_to(instance_path.resolve())
        except ValueError:
            continue
        if candidate.is_file():
            instance.update(
                launch_target=str(candidate.relative_to(instance_path)).replace("\\", "/"),
                launch_kind="argfile",
                launch_args="nogui",
                installation_required=False,
            )
            return

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="NeoForge installation is incomplete: unix_args.txt was not found in generated run.sh.",
    )


async def install_neoforge_server(instance_path: Path, instance: dict, installer_path: Path, task_record: dict | None) -> None:
    """NeoForge 설치기를 실행하고 생성된 unix 인수 파일을 시작 파일로 연결합니다."""
    java_path = Path(instance["java_path"])
    if not java_path.is_file():
        # A newly created instance has no settings screen yet, so choose an
        # installed Java 21 runtime first (or the newest available fallback).
        from modules.java_runtimes import detect_java_runtimes
        runtimes = detect_java_runtimes()
        preferred = next((runtime for runtime in runtimes if runtime["major_version"] == 21), runtimes[-1] if runtimes else None)
        if not preferred:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="NeoForge 설치에 사용할 Java를 찾을 수 없습니다. 관리자 페이지에서 Java를 먼저 설치해 주세요.")
        java_path = Path(preferred["path"])
        instance["java_path"] = str(java_path)
    if task_record:
        update_progress(task_record, 55, "NeoForge 설치 프로그램을 시작하는 중입니다.", indeterminate=True)

    def run_installer() -> subprocess.CompletedProcess:
        """이벤트 루프를 막지 않도록 NeoForge 설치기를 별도 작업에서 실행합니다."""
        process = subprocess.Popen(
            [str(java_path), "-jar", str(installer_path), "--installServer"],
            cwd=instance_path,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        output_lines = []
        assert process.stdout is not None
        deadline = time.monotonic() + 900
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    process.kill()
                    raise subprocess.TimeoutExpired(process.args, 900)
                for _, _ in selector.select(timeout=1):
                    raw_line = process.stdout.readline()
                    if not raw_line:
                        continue
                    line = raw_line.strip()
                    output_lines.append(raw_line)
                    if task_record and line:
                        # The installer has no percentage API. Its live output is the
                        # most reliable indication that dependency setup is continuing.
                        update_progress(task_record, 55, f"NeoForge 설치: {line}")
        output_lines.extend(process.stdout.readlines())
        return_code = process.wait()
        return subprocess.CompletedProcess(process.args, return_code, "".join(output_lines), "")

    try:
        result = await asyncio.to_thread(run_installer)
    except subprocess.TimeoutExpired as error:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="NeoForge 서버 설치 시간이 초과되었습니다.") from error
    except OSError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="NeoForge 설치 프로그램을 실행하지 못했습니다.") from error
    if result.returncode != 0:
        output = (result.stdout or "").strip()[-1500:]
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"NeoForge 서버 설치에 실패했습니다.\n{output}")

    # Ensure the installer created its launcher before parsing it below.
    targets = [instance_path / "run.sh"] if (instance_path / "run.sh").is_file() else []
    if not targets:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="NeoForge 설치 후 서버 실행 파일(unix_args.txt)을 찾지 못했습니다.")
    # The installer has just written its canonical launcher. Capture the
    # argfile referenced by that script before replacing run.sh ourselves.
    configure_neoforge_launch(instance_path, instance)
    write_instance(instance_path, instance)
    write_run_script(instance_path, instance)
    if task_record:
        update_progress(task_record, 90, "NeoForge 실행 구성을 저장하는 중입니다.", indeterminate=False)


@router.get("/players/{player_name}", dependencies=[Depends(require_admin)])
async def find_player(player_name: str):
    """Mojang 프로필 API로 마인크래프트 플레이어 이름을 검증합니다."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"https://api.mojang.com/users/profiles/minecraft/{player_name}")
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="유효한 Minecraft 플레이어를 찾을 수 없습니다.")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="플레이어 정보를 확인하지 못했습니다.") from error


class CatalogInstanceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    source_type: Literal["paper", "fabric", "neoforge"]
    minecraft_version: str | None = Field(default=None, max_length=30)
    loader_version: str | None = Field(default=None, max_length=60)
    neoforge_version: str | None = Field(default=None, max_length=60)


def read_text_file(instance_path: Path, filename: str) -> str:
    """서버가 생성한 선택 텍스트 파일만 읽고 없으면 새로 만들지 않습니다."""
    path = instance_path / filename
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def write_text_file(instance_path: Path, filename: str, content: str) -> None:
    """서버가 이미 생성한 텍스트 설정 파일만 수정합니다."""
    path = instance_path / filename
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="서버를 시작해 설정 파일을 생성한 뒤 수정할 수 있습니다.")
    path.write_text(content, encoding="utf-8")


@router.get("")
async def list_instances():
    """유효한 인스턴스 폴더를 최신 생성 순으로 반환합니다."""
    instances = []
    for instance_path in INSTANCE_DIR.iterdir():
        metadata_path = instance_path / "instance.json"
        if not instance_path.is_dir() or not metadata_path.is_file():
            continue
        try:
            instance = synchronize_status(instance_path)
            instance["resource_metrics"] = process_metrics(instance["id"])
            instances.append(instance)
        except (OSError, ValueError):
            continue
    return sorted(instances, key=lambda instance: instance.get("created_at", ""), reverse=True)


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def create_instance(
    name: str = Form(..., min_length=1, max_length=80),
    jar_file: UploadFile = File(...),
):
    """관리자가 직접 업로드한 JAR 파일로 새 인스턴스를 생성합니다."""
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="서버 이름을 입력해 주세요.")
    if not jar_file.filename or Path(jar_file.filename).suffix.lower() != ".jar":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JAR 파일만 업로드할 수 있습니다.")

    instance_id = uuid4().hex
    instance_path = INSTANCE_DIR / instance_id
    instance_path.mkdir()
    jar_filename = Path(jar_file.filename).name
    jar_path = instance_path / jar_filename

    try:
        size = 0
        with jar_path.open("wb") as destination:
            while chunk := await jar_file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_JAR_SIZE_BYTES:
                    raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="JAR 파일은 200MB 이하만 업로드할 수 있습니다.")
                destination.write(chunk)

        instance = {
            "id": instance_id,
            "name": clean_name,
            "jar_filename": jar_filename,
            "jar_size": size,
            "status": "stopped",
            "java_path": DEFAULT_JAVA_PATH,
            "jvm_args": DEFAULT_JVM_ARGS,
            "memory_mb": 2048,
            "launch_target": jar_filename,
            "launch_kind": "jar",
            "launch_args": "nogui",
            "source_type": "upload",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        write_instance(instance_path, instance)
        write_run_script(instance_path, instance)
        return instance
    except Exception:
        shutil.rmtree(instance_path, ignore_errors=True)
        raise
    finally:
        await jar_file.close()


@router.post("/download", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_admin)])
async def queue_catalog_instance(request: CatalogInstanceRequest):
    """페이지를 닫아도 계속되도록 카탈로그 서버 다운로드를 작업으로 등록합니다."""
    task = start_task(
        f"{request.name.strip() or '새 인스턴스'} 생성",
        lambda record: create_catalog_instance(request, record),
    )
    return task


@router.post("/download-now", status_code=status.HTTP_201_CREATED, include_in_schema=False, dependencies=[Depends(require_admin)])
async def create_catalog_instance(request: CatalogInstanceRequest, task_record: dict | None = None):
    """선택한 공식 서버 파일을 내려받아 인스턴스 폴더를 생성합니다."""
    clean_name = request.name.strip()
    if not clean_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="서버 이름을 입력해 주세요.")

    if request.source_type == "paper":
        if not request.minecraft_version:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="마인크래프트 버전을 선택해 주세요.")
        download_url = await paper_download_url(request.minecraft_version)
        official_filename = None
        source_metadata = {"minecraft_version": request.minecraft_version}
    elif request.source_type == "fabric":
        if not request.minecraft_version or not request.loader_version:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="마인크래프트와 Fabric Loader 버전을 선택해 주세요.")
        download_url, official_filename = await fabric_download(request.minecraft_version, request.loader_version)
        source_metadata = {"minecraft_version": request.minecraft_version, "loader_version": request.loader_version}
    else:
        if not request.neoforge_version:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="NeoForge 버전을 선택해 주세요.")
        download_url = neoforge_download_url(request.neoforge_version)
        official_filename = None
        source_metadata = {"minecraft_version": request.minecraft_version, "neoforge_version": request.neoforge_version, "installation_required": True}

    instance_id = uuid4().hex
    instance_path = INSTANCE_DIR / instance_id
    instance_path.mkdir()
    try:
        downloaded_path, jar_size = await download_remote_file(
            download_url, instance_path,
            on_progress=(lambda progress: update_progress(task_record, progress)) if task_record else None,
            filename=official_filename if request.source_type == "fabric" else None,
        )
        target_filename = downloaded_path.name
        instance = {
            "id": instance_id,
            "name": clean_name,
            "source_type": request.source_type,
            "jar_filename": target_filename,
            "jar_size": jar_size,
            "launch_target": target_filename,
            "launch_kind": "jar",
            "status": "stopped",
            "java_path": DEFAULT_JAVA_PATH,
            "jvm_args": DEFAULT_JVM_ARGS,
            "memory_mb": 2048,
            "launch_args": "nogui",
            "created_at": datetime.now(timezone.utc).isoformat(),
            **source_metadata,
        }
        write_instance(instance_path, instance)
        if request.source_type == "neoforge":
            # The downloaded NeoForge JAR is an installer, not the server launcher.
            await install_neoforge_server(instance_path, instance, downloaded_path, task_record)
        else:
            write_run_script(instance_path, instance)
        return instance
    except Exception:
        shutil.rmtree(instance_path, ignore_errors=True)
        raise


@router.get("/{instance_id}")
async def get_instance(instance_id: str):
    """인스턴스 하나의 메타데이터를 반환합니다."""
    instance_path = get_instance_path(instance_id)
    return read_instance(instance_path)


@router.get("/{instance_id}/server-icon")
async def get_server_icon(instance_id: str):
    """인스턴스의 선택 사항인 64x64 PNG 아이콘을 반환합니다."""
    icon_path = get_instance_path(instance_id) / "server-icon.png"
    if not icon_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="서버 아이콘을 찾을 수 없습니다.")
    return FileResponse(icon_path, media_type="image/png")


@router.post("/{instance_id}/server-icon", dependencies=[Depends(require_admin)])
async def upload_server_icon(instance_id: str, icon_file: UploadFile = File(...)):
    """64x64 PNG server-icon.png 파일인지 검증한 뒤 저장합니다."""
    if Path(icon_file.filename or "").suffix.lower() != ".png":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PNG 파일만 서버 아이콘으로 업로드할 수 있습니다.")
    try:
        content = await icon_file.read(MAX_SERVER_ICON_BYTES + 1)
    finally:
        await icon_file.close()
    if len(content) > MAX_SERVER_ICON_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="서버 아이콘은 2MB 이하여야 합니다.")
    if len(content) < 24 or content[:8] != b"\x89PNG\r\n\x1a\n":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="올바른 PNG 파일이 아닙니다.")
    width, height = struct.unpack(">II", content[16:24])
    if (width, height) != (64, 64):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="서버 아이콘은 정확히 64 × 64 픽셀이어야 합니다.")
    instance_path = get_instance_path(instance_id)
    (instance_path / "server-icon.png").write_bytes(content)
    instance = read_instance(instance_path)
    instance["server_icon_updated_at"] = datetime.now(timezone.utc).isoformat()
    write_instance(instance_path, instance)
    return instance


@router.delete("/{instance_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_instance(instance_id: str):
    """정지된 인스턴스와 폴더 안의 모든 서버 파일을 삭제합니다."""
    instance_path = get_instance_path(instance_id)
    instance = read_instance(instance_path)
    if instance.get("status") in {"running", "starting", "stopping"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="실행 중인 인스턴스는 정지한 후 삭제해 주세요.",
        )
    shutil.rmtree(instance_path)


@router.get("/{instance_id}/runtime")
async def get_runtime_settings(instance_id: str):
    """run.sh 생성에 쓰이는 JVM 실행 설정을 반환합니다."""
    instance = read_instance(get_instance_path(instance_id))
    return {key: instance.get(key, "" if key in {"jvm_args", "custom_command"} else None) for key in ("java_path", "memory_mb", "jvm_args", "launch_mode", "custom_command", "launch_target", "launch_kind")}


@router.put("/{instance_id}/name", dependencies=[Depends(require_admin)])
async def update_instance_name(instance_id: str, update: NameUpdate):
    """실제 폴더 ID는 유지한 채 인스턴스 표시 이름만 변경합니다."""
    instance_path = get_instance_path(instance_id)
    instance = read_instance(instance_path)
    instance["name"] = update.name.strip()
    if not instance["name"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="서버 이름을 입력해 주세요.")
    write_instance(instance_path, instance)
    return instance


@router.put("/{instance_id}/runtime", dependencies=[Depends(require_admin)])
async def update_runtime_settings(instance_id: str, update: RuntimeUpdate):
    """JVM 인수를 저장하고 인스턴스 시작 스크립트를 다시 생성합니다."""
    instance_path = get_instance_path(instance_id)
    instance = read_instance(instance_path)
    instance["jvm_args"] = without_memory_jvm_args(update.jvm_args)
    instance["java_path"] = update.java_path or instance.get("java_path", DEFAULT_JAVA_PATH)
    instance["memory_mb"] = update.memory_mb
    instance["launch_mode"] = update.launch_mode
    instance["custom_command"] = update.custom_command.strip()
    if instance.get("source_type") != "neoforge":
        launch_file = resolve_instance_file(instance_path, update.launch_target.strip())
        instance["launch_target"] = str(launch_file.relative_to(instance_path)).replace("\\", "/")
    write_instance(instance_path, instance)
    write_run_script(instance_path, instance)
    return {key: instance.get(key) for key in ("java_path", "memory_mb", "jvm_args", "launch_mode", "custom_command", "launch_target", "launch_kind")}


@router.get("/system/runtime-options")
async def runtime_options():
    """실행 설정 화면에 표시할 Java 선택지와 메모리 한도를 반환합니다."""
    from modules.java_runtimes import detect_java_runtimes
    memory_mb = int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 / 1024)
    return {"java_runtimes": detect_java_runtimes(), "max_memory_mb": max(256, memory_mb)}


@router.get("/{instance_id}/server-properties")
async def get_server_properties(instance_id: str):
    """서버가 생성한 경우에만 server.properties 내용을 읽습니다."""
    instance_path = get_instance_path(instance_id)
    return {"content": read_text_file(instance_path, "server.properties"), "exists": (instance_path / "server.properties").is_file()}


@router.put("/{instance_id}/server-properties", dependencies=[Depends(require_admin)])
async def update_server_properties(instance_id: str, update: TextUpdate):
    """이미 있는 server.properties 파일 내용을 저장합니다."""
    instance_path = get_instance_path(instance_id)
    write_text_file(instance_path, "server.properties", update.content)
    return {"content": update.content}


@router.get("/{instance_id}/eula")
async def get_eula(instance_id: str):
    """서버가 생성한 경우에만 eula.txt 내용을 읽습니다."""
    instance_path = get_instance_path(instance_id)
    return {"content": read_text_file(instance_path, "eula.txt"), "exists": (instance_path / "eula.txt").is_file()}


@router.put("/{instance_id}/eula", dependencies=[Depends(require_admin)])
async def update_eula(instance_id: str, update: TextUpdate):
    """이미 있는 eula.txt 파일 내용을 저장합니다."""
    instance_path = get_instance_path(instance_id)
    write_text_file(instance_path, "eula.txt", update.content)
    return {"content": update.content}


@router.get("/{instance_id}/whitelist")
async def get_whitelist(instance_id: str):
    """생성된 화이트리스트 파일을 플레이어 이름 목록으로 읽습니다."""
    instance_path = get_instance_path(instance_id)
    path = instance_path / "whitelist.json"
    return {"names": __import__("json").loads(read_text_file(instance_path, "whitelist.json")) if path.is_file() else [], "exists": path.is_file()}


@router.put("/{instance_id}/whitelist", dependencies=[Depends(require_admin)])
async def update_whitelist(instance_id: str, update: NameListUpdate):
    """전달받은 플레이어 이름 목록을 화이트리스트 파일에 저장합니다."""
    instance_path = get_instance_path(instance_id)
    if not (instance_path / "whitelist.json").is_file():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="서버를 시작해 설정 파일을 생성한 뒤 수정할 수 있습니다.")
    names = sorted({name.strip() for name in update.names if name.strip()})
    write_text_file(instance_path, "whitelist.json", __import__("json").dumps(names, ensure_ascii=False, indent=2))
    return {"names": names}


@router.get("/{instance_id}/blacklist")
async def get_blacklist(instance_id: str):
    """생성된 블랙리스트 파일을 플레이어 이름 목록으로 읽습니다."""
    instance_path = get_instance_path(instance_id)
    path = instance_path / "banned-players.json"
    return {"names": __import__("json").loads(read_text_file(instance_path, "banned-players.json")) if path.is_file() else [], "exists": path.is_file()}


@router.put("/{instance_id}/blacklist", dependencies=[Depends(require_admin)])
async def update_blacklist(instance_id: str, update: NameListUpdate):
    """전달받은 플레이어 이름 목록을 블랙리스트 파일에 저장합니다."""
    instance_path = get_instance_path(instance_id)
    if not (instance_path / "banned-players.json").is_file():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="서버를 시작해 설정 파일을 생성한 뒤 수정할 수 있습니다.")
    names = sorted({name.strip() for name in update.names if name.strip()})
    write_text_file(instance_path, "banned-players.json", __import__("json").dumps(names, ensure_ascii=False, indent=2))
    return {"names": names}


@router.get("/{instance_id}/storage/{area}")
async def browse_storage(instance_id: str, area: StorageArea, path: str = ""):
    """월드·모드·플러그인·로그 탐색기의 현재 폴더 항목을 반환합니다."""
    root = storage_root(get_instance_path(instance_id), area)
    if not root.is_dir():
        return {"exists": False, "path": "", "entries": []}
    return {"exists": True, "path": path, "entries": list_directory(root, path)}


@router.get("/{instance_id}/storage/{area}/text/{file_path:path}")
async def read_storage_text_file(instance_id: str, area: StorageArea, file_path: str):
    """탐색기의 읽기 전용 미리 보기에 사용할 작은 UTF-8 텍스트를 반환합니다."""
    target_path = safe_file_path(get_instance_path(instance_id), area, file_path)
    if not target_path.is_file() or not is_text_file(target_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="읽을 수 있는 텍스트 파일이 아닙니다.")
    if target_path.stat().st_size > MAX_TEXT_VIEW_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="2MB 이하의 텍스트 파일만 화면에서 볼 수 있습니다.")
    try:
        return {"name": target_path.name, "content": target_path.read_text(encoding="utf-8")}
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="UTF-8 텍스트 파일만 화면에서 볼 수 있습니다.") from error


@router.get("/{instance_id}/storage/{area}/{file_path:path}")
async def download_storage_file(instance_id: str, area: StorageArea, file_path: str):
    """허용된 탐색기 폴더 안의 파일 하나를 다운로드합니다."""
    target_path = safe_file_path(get_instance_path(instance_id), area, file_path)
    if not target_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="다운로드할 파일을 찾을 수 없습니다.")
    return FileResponse(target_path, filename=target_path.name)


@router.post("/{instance_id}/storage/{area}/upload", dependencies=[Depends(require_admin)])
async def upload_storage_files(
    instance_id: str,
    area: StorageArea,
    files: list[UploadFile] = File(...),
    path: str = "",
):
    """파일명 경로는 무시하고 현재 안전한 폴더에 여러 파일을 업로드합니다."""
    root = storage_root(get_instance_path(instance_id), area)
    if not root.is_dir():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="서버가 먼저 이 폴더를 생성한 뒤 업로드할 수 있습니다.")
    destination = safe_file_path(get_instance_path(instance_id), area, path)
    if not destination.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업로드할 폴더를 찾을 수 없습니다.")

    saved = []
    try:
        for upload in files:
            filename = Path(upload.filename or "").name
            if not filename or filename in {".", ".."}:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="올바른 파일 이름이 아닙니다.")
            target = destination / filename
            with target.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    output.write(chunk)
            saved.append(filename)
    finally:
        for upload in files:
            await upload.close()
    return {"uploaded": saved}


@router.post("/{instance_id}/storage/world/upload-directory", dependencies=[Depends(require_admin)])
async def upload_world_directory(instance_id: str, files: list[UploadFile] = File(...), path: str = ""):
    """브라우저에서 선택한 world 폴더 구조를 하위 경로까지 유지해 업로드합니다."""
    root = storage_root(get_instance_path(instance_id), "world")
    if not root.is_dir():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="서버가 먼저 world 폴더를 생성한 뒤 업로드할 수 있습니다.")
    destination = safe_file_path(get_instance_path(instance_id), "world", path)
    if not destination.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="업로드할 폴더를 찾을 수 없습니다.")

    saved = []
    try:
        for upload in files:
            relative = PurePosixPath((upload.filename or "").replace("\\", "/"))
            # Browser folder uploads include the selected root folder as the
            # first component. Omit it so its contents go directly into world.
            parts = relative.parts[1:]
            if not parts or relative.is_absolute() or any(part in {"", ".", ".."} for part in parts):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="올바른 월드 폴더 경로가 아닙니다.")
            target = (destination.joinpath(*parts)).resolve()
            try:
                target.relative_to(destination.resolve())
            except ValueError as error:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="허용되지 않는 업로드 경로입니다.") from error
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    output.write(chunk)
            saved.append(str(target.relative_to(destination)).replace("\\", "/"))
    finally:
        for upload in files:
            await upload.close()
    return {"uploaded": saved}


@router.delete("/{instance_id}/storage/{area}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def clear_storage_directory(instance_id: str, area: StorageArea):
    """최상위 월드·모드·플러그인 폴더는 남기고 내부만 비웁니다."""
    if area == "logs":
        raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="로그 폴더 전체 삭제는 지원하지 않습니다.")
    root = storage_root(get_instance_path(instance_id), area)
    if not root.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="비울 폴더를 찾을 수 없습니다.")
    for entry in root.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


@router.delete("/{instance_id}/storage/{area}/{file_path:path}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
async def delete_storage_entry(instance_id: str, area: StorageArea, file_path: str):
    """허용된 탐색기 폴더 안에서만 선택한 파일 또는 폴더를 삭제합니다."""
    target_path = safe_file_path(get_instance_path(instance_id), area, file_path)
    if not target_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="삭제할 항목을 찾을 수 없습니다.")
    if target_path.is_dir():
        shutil.rmtree(target_path)
    else:
        target_path.unlink()


@router.get("/{instance_id}/extensions")
async def get_extensions(instance_id: str):
    """서버가 만든 모드·플러그인·config 폴더의 존재 여부를 반환합니다."""
    instance_path = get_instance_path(instance_id)
    return {kind: {"exists": (instance_path / kind).is_dir()} for kind in ("mods", "plugins", "config")}


@router.get("/{instance_id}/world/download")
async def download_world(instance_id: str):
    """world 폴더 전체를 포함한 ZIP 파일을 만들어 다운로드합니다."""
    source = get_instance_path(instance_id) / "world"
    if not source.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="아직 생성된 world 폴더가 없습니다.")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in source.rglob("*"):
            if file_path.is_file(): zip_file.write(file_path, file_path.relative_to(source.parent))
    archive.seek(0)
    return StreamingResponse(archive, media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="world.zip"'})


@router.post("/{instance_id}/start")
async def start_instance(instance_id: str):
    """인스턴스 전용 폴더에서 생성된 run.sh를 실행합니다."""
    return start_process(get_instance_path(instance_id))


@router.post("/{instance_id}/stop")
async def stop_instance(instance_id: str):
    """백엔드가 시작한 인스턴스 서버에 정상 종료를 요청합니다."""
    return stop_process(get_instance_path(instance_id))


@router.post("/{instance_id}/force-stop", dependencies=[Depends(require_admin)])
async def force_stop_instance(instance_id: str):
    """응답하지 않는 인스턴스 서버 프로세스를 즉시 강제 종료합니다."""
    return force_stop(get_instance_path(instance_id))


@router.websocket("/{instance_id}/console")
async def console_socket(websocket: WebSocket, instance_id: str, token: str | None = None):
    """WebSocket으로 실시간 로그를 보내고 콘솔 입력을 서버로 전달합니다."""
    get_instance_path(instance_id); await websocket.accept()
    role = session_role(token)
    if role not in {"admin", "user"}:
        await websocket.close(code=1008)
        return
    sent = 0
    try:
        while True:
            total, lines = console_snapshot(instance_id)
            # The buffer retains only 500 lines, while `total` keeps growing.
            # Translate the client cursor into the current buffer window so
            # the live console continues after the buffer first fills.
            first_buffered = max(total - len(lines), 0)
            if total < sent:  # A server restart reset the in-memory console.
                sent = 0
            sent = max(sent, first_buffered)
            for line in lines[sent - first_buffered:]:
                await websocket.send_json({"type": "log", "line": line})
            sent = total
            try:
                command = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                await websocket.send_json({"type": "command", "accepted": role == "admin" and send_command(instance_id, command)})
            except asyncio.TimeoutError:
                continue
    except WebSocketDisconnect:
        return
