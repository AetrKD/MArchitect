"""Container-visible resource metrics for the server dashboard."""
import shutil
import time
from pathlib import Path

from fastapi import APIRouter

from modules.instance_store import INSTANCE_DIR

router = APIRouter(prefix="/system", tags=["system"])
_previous_network: tuple[float, int, int] | None = None


def read_network_bytes() -> tuple[int, int]:
    """루프백을 제외한 컨테이너 네트워크 송수신 바이트를 합산합니다."""
    received = sent = 0
    for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
        name, values = line.split(":", 1)
        if name.strip() == "lo":
            continue
        counters = values.split()
        received += int(counters[0])
        sent += int(counters[8])
    return received, sent


@router.get("/metrics")
async def system_metrics():
    """대시보드용 디스크 사용량과 네트워크 전송 속도 표본을 반환합니다."""
    global _previous_network
    received, sent = read_network_bytes()
    now = time.monotonic()
    if _previous_network:
        elapsed = max(now - _previous_network[0], 0.001)
        download_bps = round((received - _previous_network[1]) / elapsed)
        upload_bps = round((sent - _previous_network[2]) / elapsed)
    else:
        download_bps = upload_bps = 0
    _previous_network = (now, received, sent)

    disk = shutil.disk_usage(INSTANCE_DIR)
    return {
        "disk_used": disk.used,
        "disk_total": disk.total,
        "network_download_bps": max(0, download_bps),
        "network_upload_bps": max(0, upload_bps),
    }
