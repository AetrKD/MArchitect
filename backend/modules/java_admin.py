"""Administrator endpoints for downloading, detecting and removing Java runtimes."""
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from modules.downloads import USER_AGENT, download_file
from modules.java_runtimes import detect_java_runtimes
from modules.task_store import start_task, update_progress

router = APIRouter(prefix="/admin/java-runtimes", tags=["admin-java-runtimes"])
JAVA_INSTALL_DIR = Path(os.getenv("MARCHITECT_JAVA_INSTALL_DIR", "/java"))
ADOPTIUM_API_URL = "https://api.adoptium.net/v3"


class RuntimeDownloadRequest(BaseModel):
    major_version: int = Field(ge=8, le=25)


def safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    """압축 내부 경로가 대상 폴더를 벗어나지 않을 때만 Java를 풉니다."""
    destination = destination.resolve()
    for member in archive.getmembers():
        target = (destination / member.name).resolve()
        if not str(target).startswith(f"{destination}{os.sep}"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="안전하지 않은 Java 압축 파일입니다.")
    archive.extractall(destination)


@router.get("")
async def installed_java_runtimes():
    """감지된 런타임과 앱이 JAVA 폴더에서 관리하는 항목을 반환합니다."""
    install_root = JAVA_INSTALL_DIR.resolve()
    runtimes = []
    for runtime in detect_java_runtimes():
        executable = Path(runtime["path"])
        runtime_dir = executable.parent.parent
        if runtime_dir.parent == install_root:
            runtime["managed_directory"] = runtime_dir.name
        runtimes.append(runtime)
    return runtimes


@router.get("/available")
async def available_java_versions():
    """Adoptium에서 설치 가능한 Temurin 주요 버전 목록을 읽습니다."""
    try:
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(f"{ADOPTIUM_API_URL}/info/available_releases")
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Temurin 버전 목록을 불러오지 못했습니다.") from error

    return [version for version in data.get("available_releases", []) if 8 <= version <= 25]


@router.delete("/{directory_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_java_runtime(directory_name: str):
    """앱이 /java 아래에서 관리하는 Java 런타임만 삭제합니다."""
    if Path(directory_name).name != directory_name or directory_name in {"", ".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="올바른 Java 폴더 이름을 지정해 주세요.")

    install_root = JAVA_INSTALL_DIR.resolve()
    runtime_path = (install_root / directory_name).resolve()
    try:
        runtime_path.relative_to(install_root)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="삭제할 수 없는 Java 경로입니다.") from error

    if runtime_path.parent != install_root or not (runtime_path / "bin" / "java").is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="설치된 Java를 찾을 수 없습니다.")

    shutil.rmtree(runtime_path)


@router.post("/download", status_code=status.HTTP_202_ACCEPTED)
async def queue_java_runtime_download(request: RuntimeDownloadRequest):
    """페이지를 나가도 계속되도록 Java 다운로드를 백그라운드에 등록합니다."""
    task = start_task(
        f"Java {request.major_version} 다운로드",
        lambda record: download_java_runtime(request, record),
    )
    return task


@router.post("/download-now", status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def download_java_runtime(request: RuntimeDownloadRequest, task_record: dict | None = None):
    """Temurin을 다운로드·압축 해제하고 진행 상태를 작업 기록에 남깁니다."""
    try:
        async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(
                f"{ADOPTIUM_API_URL}/assets/latest/{request.major_version}/hotspot",
                params={"architecture": "x64", "image_type": "jdk", "os": "linux", "vendor": "eclipse"},
            )
            response.raise_for_status()
            assets = response.json()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Temurin Java 정보를 불러오지 못했습니다.") from error

    if not assets:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="선택한 Temurin Linux x64 Java를 찾을 수 없습니다.")

    package = assets[0]["binary"]["package"]
    JAVA_INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path = Path(tempfile.mkdtemp(prefix=f"marchitect-java-{request.major_version}-"))
    archive_path = temporary_path / "runtime.tar.gz"
    try:
        await download_file(
            package["link"], archive_path, max_size_bytes=512 * 1024 * 1024,
            on_progress=(lambda progress: update_progress(task_record, progress)) if task_record else None,
        )
        extract_path = temporary_path / "extract"
        extract_path.mkdir()
        with tarfile.open(archive_path, "r:gz") as archive:
            safe_extract(archive, extract_path)
        extracted_root = next((path for path in extract_path.iterdir() if (path / "bin" / "java").is_file()), None)
        if not extracted_root:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="다운로드한 Temurin Java의 구조가 올바르지 않습니다.")
        # Preserve the distribution's original directory name so multiple
        # Java 24 distributions can coexist under backend/JAVA.
        runtime_path = JAVA_INSTALL_DIR / extracted_root.name
        if runtime_path.exists():
            if (runtime_path / "bin" / "java").is_file():
                return {"message": "이미 설치되어 있습니다.", "path": str(runtime_path / "bin" / "java")}
            shutil.rmtree(runtime_path)
        shutil.copytree(extracted_root, runtime_path)
    finally:
        shutil.rmtree(temporary_path, ignore_errors=True)
    return {"message": "Temurin Java를 설치했습니다.", "path": str(runtime_path / "bin" / "java"), "sha256": package.get("checksum")}
