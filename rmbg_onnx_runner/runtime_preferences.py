from __future__ import annotations

import json
from pathlib import Path, PurePosixPath


def _valid_model_id(value: object) -> bool:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        return False
    return ".." not in PurePosixPath(value.replace("\\", "/")).parts


def load_last_model(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    value = payload.get("lastModel") if isinstance(payload, dict) and payload.get("schemaVersion") == 1 else None
    return value if _valid_model_id(value) else ""


def save_last_model(path: Path, model_id: str) -> None:
    if not _valid_model_id(model_id):
        raise ValueError("last model must be a safe relative model ID")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(json.dumps({"schemaVersion": 1, "lastModel": model_id}, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
