"""Filesystem heartbeat shared by the email worker and API process."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def heartbeat_path() -> Path | None:
    value = os.getenv("EMAIL_WORKER_HEARTBEAT_FILE", "").strip()
    return Path(value) if value else None


def write_worker_heartbeat(result: dict, status: str = "healthy") -> None:
    path = heartbeat_path()
    if path is None:
        return
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "processed": int(result.get("processed", 0)),
        "sent": int(result.get("sent", 0)),
        "failed": int(result.get("failed", 0)),
        "retried": int(result.get("retried", 0)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    temporary.replace(path)


def read_worker_heartbeat() -> dict | None:
    path = heartbeat_path()
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            key: payload.get(key)
            for key in ("timestamp", "status", "processed", "sent", "failed", "retried")
        }
    except (OSError, ValueError, TypeError):
        return None
