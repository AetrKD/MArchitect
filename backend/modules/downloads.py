"""Safe streaming download helpers used by Java and server catalogs."""
import re
from pathlib import Path
from urllib.parse import unquote
from collections.abc import Callable

import httpx
from fastapi import HTTPException, status

USER_AGENT = "MArchitect/0.1"


async def download_file(url: str, destination: Path, max_size_bytes: int = 512 * 1024 * 1024, on_progress: Callable[[int], None] | None = None) -> int:
    """허용된 제공처의 파일을 크기 제한과 함께 조각 단위로 다운로드합니다."""
    size = 0
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0, headers={"User-Agent": USER_AGENT}) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", "0"))
                with destination.open("wb") as output:
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        size += len(chunk)
                        if size > max_size_bytes:
                            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="다운로드 파일이 허용 크기를 초과했습니다.")
                        output.write(chunk)
                        if on_progress and total:
                            on_progress(int(size * 100 / total))
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    except httpx.HTTPError as error:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="공식 다운로드 서버에서 파일을 가져오지 못했습니다.") from error
    return size


def remote_filename(url: str, content_disposition: str | None) -> str:
    """제공처의 파일명을 우선 사용하고 없으면 URL에서 안전한 이름을 얻습니다."""
    match = re.search(r"filename\*?=(?:UTF-8''|\")?([^;\"]+)", content_disposition or "", flags=re.IGNORECASE)
    candidate = match.group(1).strip() if match else url.rsplit("/", 1)[-1]
    filename = Path(unquote(candidate)).name
    return filename or "downloaded-server-file"


async def download_remote_file(url: str, destination_directory: Path, max_size_bytes: int = 512 * 1024 * 1024, on_progress: Callable[[int], None] | None = None, filename: str | None = None) -> tuple[Path, int]:
    """공식 제공처가 알려준 원래 파일명으로 서버 JAR을 내려받습니다."""
    size = 0
    target_path: Path | None = None
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0, headers={"User-Agent": USER_AGENT}) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                target_path = destination_directory / (filename or remote_filename(url, response.headers.get("content-disposition")))
                total = int(response.headers.get("content-length", "0"))
                with target_path.open("wb") as output:
                    async for chunk in response.aiter_bytes(1024 * 1024):
                        size += len(chunk)
                        if size > max_size_bytes:
                            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="다운로드 파일이 허용 크기를 초과했습니다.")
                        output.write(chunk)
                        if on_progress and total:
                            on_progress(int(size * 100 / total))
    except HTTPException:
        if target_path:
            target_path.unlink(missing_ok=True)
        raise
    except httpx.HTTPError as error:
        if target_path:
            target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="공식 다운로드 서버에서 파일을 가져오지 못했습니다.") from error
    if not target_path:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="다운로드 파일 이름을 확인하지 못했습니다.")
    return target_path, size
