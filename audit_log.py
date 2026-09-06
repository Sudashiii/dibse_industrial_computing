"""JSON Lines audit log storage for the local MCP server."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_AUDIT_LOG_PATH = PROJECT_ROOT / "data" / "audit_events.jsonl"
_AUDIT_FILE_LOCK = Lock()


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def append_audit_event(
    event_type: str,
    message: str,
    details: dict[str, Any] | None = None,
    log_path: Path | str = DEFAULT_AUDIT_LOG_PATH,
) -> dict[str, Any]:
    """Append one JSON event to the local audit log and return the event."""

    cleaned_event_type = _require_text(event_type, "event_type")
    cleaned_message = _require_text(message, "message")
    event_details = {} if details is None else dict(details)

    event = {
        "event_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event_type": cleaned_event_type,
        "message": cleaned_message,
        "details": event_details,
    }

    try:
        serialized_event = json.dumps(event, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as error:
        raise ValueError("details must contain only JSON-serializable values") from error

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _AUDIT_FILE_LOCK:
        with path.open("a", encoding="utf-8", newline="\n") as audit_file:
            audit_file.write(serialized_event + "\n")

    return {"success": True, "event": event}


def read_audit_log(log_path: Path | str = DEFAULT_AUDIT_LOG_PATH) -> str:
    """Return the raw JSONL audit log, or an empty string if it is missing."""

    path = Path(log_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")
