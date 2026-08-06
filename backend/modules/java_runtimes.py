"""Java runtime discovery inside configured container directories."""
import os
import re
import subprocess
from hashlib import sha256
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/java-runtimes", tags=["java-runtimes"])

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RUNTIME_ROOTS = [Path("/java"), Path("/usr/lib/jvm"), BACKEND_DIR / "java"]


def configured_runtime_roots() -> list[Path]:
    """Java 런타임이 있을 수 있도록 설정된 최상위 폴더 목록을 반환합니다."""
    configured_roots = os.getenv("MARCHITECT_JAVA_ROOTS")
    if not configured_roots:
        return DEFAULT_RUNTIME_ROOTS
    return [Path(path) for path in configured_roots.split(os.pathsep) if path]


def find_java_executables() -> list[Path]:
    """설정된 Java 폴더 밖으로 벗어나지 않으며 실행 가능한 java를 찾습니다."""
    executables = []
    seen_paths = set()
    executable_names = ("java", "java.exe")

    for root in configured_runtime_roots():
        if not root.is_dir():
            continue
        for executable_name in executable_names:
            for executable in root.glob(f"**/bin/{executable_name}"):
                resolved_path = executable.resolve()
                if resolved_path in seen_paths or not os.access(resolved_path, os.X_OK):
                    continue
                seen_paths.add(resolved_path)
                executables.append(resolved_path)
    return executables


def inspect_java(executable: Path) -> dict | None:
    """java -version 결과를 실행 경로·버전·배포판 정보로 변환합니다."""
    try:
        result = subprocess.run(
            [str(executable), "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    output = f"{result.stdout}\n{result.stderr}".strip()
    version_match = re.search(r'version\s+"([^"]+)"', output)
    if result.returncode != 0 or not version_match:
        return None

    version = version_match.group(1)
    try:
        major_version = int(version.split(".")[1]) if version.startswith("1.") else int(version.split(".")[0])
    except (IndexError, ValueError):
        return None

    runtime_key = sha256(str(executable).encode("utf-8")).hexdigest()[:10]
    # The full `java -version` output identifies common OpenJDK distributions.
    distribution = next((name for marker, name in (
        ("Temurin", "Temurin"), ("Zulu", "Zulu"), ("Microsoft", "Microsoft OpenJDK"),
        ("Corretto", "Amazon Corretto"), ("Oracle", "Oracle JDK"),
    ) if marker.lower() in output.lower()), "OpenJDK")
    return {
        "id": f"java-{major_version}-{runtime_key}",
        "name": f"Java {major_version}",
        "version": version,
        "major_version": major_version,
        "distribution": distribution,
        "path": str(executable),
    }


def detect_java_runtimes() -> list[dict]:
    """찾아낸 유효한 Java 런타임을 검사하고 정렬합니다."""
    runtimes = [runtime for executable in find_java_executables() if (runtime := inspect_java(executable))]
    return sorted(runtimes, key=lambda runtime: (runtime["major_version"], runtime["path"]))


@router.get("")
async def list_java_runtimes():
    """컨테이너에 설정된 폴더에서 감지한 Java 런타임 목록을 반환합니다."""
    return detect_java_runtimes()
