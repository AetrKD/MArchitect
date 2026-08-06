"""Official Paper, Fabric and NeoForge catalog lookups."""
import asyncio
import xml.etree.ElementTree as element_tree

import httpx
from fastapi import APIRouter, HTTPException, status

from modules.downloads import USER_AGENT

router = APIRouter(prefix="/server-catalog", tags=["server-catalog"])

PAPER_BASE_URL = "https://fill.papermc.io/v3/projects/paper"
FABRIC_META_URL = "https://meta.fabricmc.net/v2/versions"
NEOFORGE_METADATA_URL = "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
NEOFORGE_MINECRAFT_VERSION_PREFIXES = {
    "1.21.1": ("21.1.",),
    "1.21": ("21.0.",),
    "1.20.6": ("20.6.",),
    "1.20.4": ("20.4.",),
    "1.20.2": ("20.2.",),
    "1.20.1": ("47.",),
    "1.20": ("46.",),
    "1.19.4": ("45.",),
    "1.19.3": ("44.",),
    "1.19.2": ("43.",),
    "1.19.1": ("42.",),
}


def version_sort_key(version: str) -> tuple:
    """일반 숫자 버전이 시험 버전 접미사보다 먼저 오도록 정렬 키를 만듭니다."""
    parts = version.replace("-", ".").split(".")
    return tuple(int(part) if part.isdigit() else -1 for part in parts)


def neoforge_prefixes_for_minecraft(minecraft_version: str) -> tuple[str, ...]:
    """마인크래프트 버전을 호환되는 NeoForge 로더 번호 접두사로 변환합니다."""
    special_prefixes = NEOFORGE_MINECRAFT_VERSION_PREFIXES.get(minecraft_version, ())
    modern_prefix = minecraft_version.removeprefix("1.") + "."
    return (modern_prefix, *special_prefixes)


async def get_json(url: str):
    """공식 카탈로그 JSON을 요청하고 실패하면 사용자용 오류로 바꿉니다."""
    try:
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="공식 버전 목록을 불러오지 못했습니다.") from error


async def get_paper_versions() -> list[str]:
    """Paper가 지원하는 마인크래프트 버전 목록을 반환합니다."""
    data = await get_json(f"{PAPER_BASE_URL}/versions")
    # Paper's v3 service returns a list of version objects, not the grouped
    # dictionary returned by older endpoints.
    versions = [item["version"]["id"] for item in data.get("versions", []) if item.get("version", {}).get("id")]
    return sorted(set(versions), key=version_sort_key, reverse=True)


async def get_fabric_game_versions() -> list[str]:
    """안정 버전인 Fabric 지원 마인크래프트 목록을 반환합니다."""
    versions = await get_json(f"{FABRIC_META_URL}/game")
    return [item["version"] for item in versions if item.get("stable")]


@router.get("/minecraft-versions")
async def minecraft_versions():
    """서버 종류가 함께 쓰는 마인크래프트 버전 선택 목록을 반환합니다."""
    paper, fabric = await asyncio.gather(get_paper_versions(), get_fabric_game_versions())
    # Paper/Fabric supply the authoritative visible game versions. NeoForge's
    # metadata uses loader-number formats for older releases, so it is not used
    # as the display source.
    return sorted(set(paper) | set(fabric), key=version_sort_key, reverse=True)


@router.get("/fabric/loaders/{minecraft_version}")
async def fabric_loader_versions(minecraft_version: str):
    """선택한 마인크래프트 버전에서 쓸 수 있는 안정 Fabric 로더를 반환합니다."""
    versions = await get_json(f"{FABRIC_META_URL}/loader/{minecraft_version}")
    return [item["loader"]["version"] for item in versions if item.get("loader", {}).get("stable")]


async def get_neoforge_versions() -> list[str]:
    """NeoForge Maven 메타데이터에서 로더를 읽어 최신순으로 반환합니다."""
    try:
        async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(NEOFORGE_METADATA_URL)
            response.raise_for_status()
        root = element_tree.fromstring(response.text)
    except (httpx.HTTPError, element_tree.ParseError) as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="NeoForge 버전 목록을 불러오지 못했습니다.") from error

    versions = [node.text for node in root.findall("./versioning/versions/version") if node.text]
    return list(reversed(versions))


@router.get("/neoforge/loaders/{minecraft_version}")
async def neoforge_loader_versions(minecraft_version: str):
    """선택한 마인크래프트 버전과 호환되는 NeoForge 로더만 반환합니다."""
    prefixes = neoforge_prefixes_for_minecraft(minecraft_version)
    versions = await get_neoforge_versions()
    matched_versions = [version for version in versions if version.startswith(prefixes)]
    if not matched_versions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="선택한 마인크래프트 버전에 맞는 NeoForge 로더가 없습니다.")
    return matched_versions


async def paper_download_url(minecraft_version: str) -> str:
    """마인크래프트 버전에 맞는 최신 안정 Paper JAR 주소를 찾습니다."""
    builds = await get_json(f"{PAPER_BASE_URL}/versions/{minecraft_version}/builds")
    stable_build = next((build for build in builds if build.get("channel") == "STABLE"), None)
    if not stable_build:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="선택한 Paper 안정 빌드를 찾을 수 없습니다.")
    return stable_build["downloads"]["server:default"]["url"]


async def fabric_download(minecraft_version: str, loader_version: str) -> tuple[str, str]:
    """Fabric 공식 서버 실행 파일의 주소와 원본 파일명을 반환합니다."""
    installers = await get_json(f"{FABRIC_META_URL}/installer")
    installer_version = next((item["version"] for item in installers if item.get("stable")), None)
    if not installer_version:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Fabric 설치 프로그램 버전을 찾을 수 없습니다.")
    url = f"{FABRIC_META_URL}/loader/{minecraft_version}/{loader_version}/{installer_version}/server/jar"
    filename = f"fabric-server-mc.{minecraft_version}-loader.{loader_version}-launcher.{installer_version}.jar"
    return url, filename


def neoforge_download_url(neoforge_version: str) -> str:
    """NeoForge 로더 버전에 맞는 공식 설치기 다운로드 주소를 만듭니다."""
    return f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{neoforge_version}/neoforge-{neoforge_version}-installer.jar"
