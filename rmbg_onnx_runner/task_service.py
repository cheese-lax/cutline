from __future__ import annotations

import json
import secrets
import shutil
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Iterable, Iterator
from urllib.parse import quote

import rmbg_onnx
from werkzeug.datastructures import FileStorage, MultiDict

IMAGE_EXTENSIONS = {
    ".apng",
    ".avif",
    ".avifs",
    ".bmp",
    ".dds",
    ".dib",
    ".gif",
    ".icb",
    ".ico",
    ".j2c",
    ".j2k",
    ".jfif",
    ".jp2",
    ".jpc",
    ".jpe",
    ".jpeg",
    ".jpf",
    ".jpg",
    ".jpx",
    ".pbm",
    ".pfm",
    ".pgm",
    ".png",
    ".pnm",
    ".ppm",
    ".psd",
    ".qoi",
    ".tga",
    ".tif",
    ".tiff",
    ".vda",
    ".vst",
    ".webp",
}
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class ProcessOptions:
    processing_mode: str = "rmbg"
    output_format: str = "png"
    edge_optimize: bool = False
    transparent_background: bool = True
    background_color: str = "#FFFFFF"


@dataclass(frozen=True)
class TaskHistoryEntry:
    run_id: str
    run_dir: Path
    created_at: datetime
    created_text: str
    status: str
    size_bytes: int


def safe_relative_path(raw_name: str, fallback_name: str) -> Path:
    name = (raw_name or fallback_name or "image").replace("\\", "/")
    parts = []
    for part in PurePosixPath(name).parts:
        if part in {"", ".", ".."} or part.endswith(":"):
            continue
        parts.append(part)
    if not parts:
        parts = [fallback_name or "image"]
    return Path(*parts)


def output_name(
    relative_path: Path,
    output_format: str = "png",
    processing_mode: str = "rmbg",
) -> Path:
    stem = relative_path.stem or "image"
    mode = rmbg_onnx.normalize_processing_mode(processing_mode)
    suffix = "lineart" if mode == "line_art" else "rmbg"
    extension = rmbg_onnx.normalize_output_format(output_format)
    return relative_path.with_name(f"{stem}_{suffix}.{extension}")


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def new_run_id(now: datetime | None = None, suffix: str | None = None) -> str:
    created = now or datetime.now()
    random_suffix = suffix or secrets.token_hex(2)
    return f"{created:%Y%m%d-%H%M%S}-{created.microsecond // 1000:03d}-{random_suffix}"


def process_options_payload(options: ProcessOptions) -> dict[str, object]:
    return {
        "processingMode": options.processing_mode,
        "outputFormat": options.output_format,
        "edgeOptimize": options.edge_optimize,
        "transparentBackground": options.transparent_background,
        "backgroundColor": options.background_color,
    }


def write_task_manifest(run_dir: Path, manifest: dict[str, object]) -> None:
    manifest_path = run_dir / MANIFEST_NAME
    manifest["updatedAt"] = now_text()
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_task_manifest(manifest_path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("schemaVersion") != 1:
        return None
    return payload


def load_recent_tasks(output_root: Path, limit: int = 10) -> list[dict[str, object]]:
    if not output_root.is_dir():
        return []

    tasks = []
    for run_dir in output_root.iterdir():
        if not run_dir.is_dir():
            continue
        manifest = load_task_manifest(run_dir / MANIFEST_NAME)
        if manifest is None:
            continue
        sort_key = str(manifest.get("runId") or run_dir.name)
        tasks.append((sort_key, manifest))

    tasks.sort(key=lambda item: item[0], reverse=True)
    return [manifest for _, manifest in tasks[: max(limit, 0)]]


def task_directory_size(run_dir: Path) -> int:
    total = 0
    for path in run_dir.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total


def parse_task_created_at(
    manifest: dict[str, object],
    run_dir: Path,
    timezone,
) -> tuple[datetime, str]:
    created_text = str(manifest.get("createdAt") or "").strip()
    try:
        created_at = datetime.strptime(created_text, "%Y-%m-%d %H:%M:%S")
        return created_at.replace(tzinfo=timezone), created_text
    except ValueError:
        created_at = datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone)
        return created_at, created_at.strftime("%Y-%m-%d %H:%M:%S")


def scan_task_history(
    output_root: Path,
    now: datetime | None = None,
) -> list[TaskHistoryEntry]:
    if not output_root.is_dir():
        return []
    current_time = now or datetime.now().astimezone()
    if current_time.tzinfo is None:
        current_time = current_time.astimezone()

    entries = []
    for run_dir in output_root.iterdir():
        if run_dir.is_symlink() or not run_dir.is_dir():
            continue
        manifest = load_task_manifest(run_dir / MANIFEST_NAME)
        if manifest is None or str(manifest.get("runId") or "") != run_dir.name:
            continue
        try:
            created_at, created_text = parse_task_created_at(
                manifest,
                run_dir,
                current_time.tzinfo,
            )
        except OSError:
            continue
        entries.append(
            TaskHistoryEntry(
                run_id=run_dir.name,
                run_dir=run_dir,
                created_at=created_at,
                created_text=created_text,
                status=str(manifest.get("status") or "unknown"),
                size_bytes=task_directory_size(run_dir),
            )
        )
    entries.sort(key=lambda entry: (entry.created_at, entry.run_id), reverse=True)
    return entries


def load_task_for_run(output_root: Path, run_id: str) -> dict[str, object] | None:
    raw_run_id = (run_id or "").strip()
    if (
        not raw_run_id
        or "/" in raw_run_id
        or "\\" in raw_run_id
        or raw_run_id in {".", ".."}
        or raw_run_id.endswith(":")
    ):
        return None
    run_dir = output_root / raw_run_id
    if run_dir.is_symlink() or not run_dir.is_dir():
        return None
    manifest = load_task_manifest(run_dir / MANIFEST_NAME)
    if manifest is None or str(manifest.get("runId") or "") != raw_run_id:
        return None
    return manifest


def list_task_history(
    output_root: Path,
    protected_run_ids: Iterable[str] = (),
    limit: int = 100,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    protected = {str(run_id) for run_id in protected_run_ids if run_id}
    tasks = []
    for entry in scan_task_history(output_root, now=now)[: max(limit, 0)]:
        manifest = load_task_for_run(output_root, entry.run_id)
        if manifest is None:
            continue
        items = manifest.get("items")
        first_result = next(
            (
                item
                for item in items
                if isinstance(item, dict) and item.get("ok") and item.get("outputUrl")
            ),
            None,
        ) if isinstance(items, list) else None
        tasks.append(
            {
                "runId": entry.run_id,
                "createdAt": entry.created_text,
                "updatedAt": str(manifest.get("updatedAt") or ""),
                "status": entry.status,
                "total": int(manifest.get("total") or 0),
                "success": int(manifest.get("success") or 0),
                "failed": int(manifest.get("failed") or 0),
                "sizeBytes": entry.size_bytes,
                "outputDir": str(manifest.get("outputDir") or ""),
                "previewUrl": str(first_result.get("outputUrl") or "")
                if first_result
                else "",
                "canDelete": entry.status != "running" and entry.run_id not in protected,
            }
        )
    return tasks


def delete_task_history(
    output_root: Path,
    run_ids: Iterable[str],
    protected_run_ids: Iterable[str] = (),
) -> dict[str, object]:
    protected = {str(run_id) for run_id in protected_run_ids if run_id}
    requested = list(dict.fromkeys(str(run_id) for run_id in run_ids))
    deleted_run_ids = []
    skipped_run_ids = []
    freed_bytes = 0
    for run_id in requested:
        manifest = load_task_for_run(output_root, run_id)
        if (
            manifest is None
            or run_id in protected
            or manifest.get("status") == "running"
        ):
            skipped_run_ids.append(run_id)
            continue
        run_dir = output_root / run_id
        freed_bytes += task_directory_size(run_dir)
        shutil.rmtree(run_dir)
        deleted_run_ids.append(run_id)
    return {
        "deletedTasks": len(deleted_run_ids),
        "deletedRunIds": deleted_run_ids,
        "skippedRunIds": skipped_run_ids,
        "freedBytes": freed_bytes,
        "remainingTasks": len(scan_task_history(output_root)),
    }


def task_history_summary(
    output_root: Path,
    retention_days: int = 30,
    max_tasks: int = 100,
    keep_latest: int = 10,
    protected_run_ids: Iterable[str] = (),
    now: datetime | None = None,
) -> dict[str, object]:
    if min(retention_days, max_tasks, keep_latest) < 0:
        raise ValueError("历史保留参数不能为负数。")
    current_time = now or datetime.now().astimezone()
    if current_time.tzinfo is None:
        current_time = current_time.astimezone()
    entries = scan_task_history(output_root, now=current_time)
    protected = {str(run_id) for run_id in protected_run_ids if run_id}
    completed = [entry for entry in entries if entry.status != "running"]
    protected.update(entry.run_id for entry in completed[:keep_latest])
    cutoff = current_time - timedelta(days=retention_days)

    cleanup_entries = []
    for index, entry in enumerate(completed):
        if entry.run_id in protected:
            continue
        expired = retention_days > 0 and entry.created_at < cutoff
        excess = max_tasks > 0 and index >= max_tasks
        if expired or excess:
            cleanup_entries.append(entry)
    cleanup_entries.sort(key=lambda entry: (entry.created_at, entry.run_id))

    return {
        "totalTasks": len(entries),
        "totalBytes": sum(entry.size_bytes for entry in entries),
        "oldestAt": entries[-1].created_text if entries else "",
        "newestAt": entries[0].created_text if entries else "",
        "cleanupTasks": len(cleanup_entries),
        "cleanupBytes": sum(entry.size_bytes for entry in cleanup_entries),
        "cleanupRunIds": [entry.run_id for entry in cleanup_entries],
        "skippedRunning": sum(entry.status == "running" for entry in entries),
        "policy": {
            "retentionDays": retention_days,
            "maxTasks": max_tasks,
            "keepLatest": keep_latest,
        },
    }


def cleanup_task_history(
    output_root: Path,
    retention_days: int = 30,
    max_tasks: int = 100,
    keep_latest: int = 10,
    protected_run_ids: Iterable[str] = (),
    now: datetime | None = None,
) -> dict[str, object]:
    preview = task_history_summary(
        output_root,
        retention_days=retention_days,
        max_tasks=max_tasks,
        keep_latest=keep_latest,
        protected_run_ids=protected_run_ids,
        now=now,
    )
    deleted_tasks = 0
    freed_bytes = 0
    for run_id in preview["cleanupRunIds"]:
        run_dir = output_root / str(run_id)
        if run_dir.is_symlink() or not run_dir.is_dir():
            continue
        manifest = load_task_manifest(run_dir / MANIFEST_NAME)
        if (
            manifest is None
            or str(manifest.get("runId") or "") != run_dir.name
            or manifest.get("status") == "running"
        ):
            continue
        size_bytes = task_directory_size(run_dir)
        shutil.rmtree(run_dir)
        deleted_tasks += 1
        freed_bytes += size_bytes

    remaining = scan_task_history(output_root, now=now)
    return {
        "deletedTasks": deleted_tasks,
        "freedBytes": freed_bytes,
        "remainingTasks": len(remaining),
        "policy": preview["policy"],
    }


def result_dir_for_run(output_root: Path, run_id: str) -> Path:
    raw_run_id = (run_id or "").strip()
    if not raw_run_id:
        return output_root.resolve()
    if (
        "/" in raw_run_id
        or "\\" in raw_run_id
        or raw_run_id in {".", ".."}
        or raw_run_id.endswith(":")
    ):
        raise ValueError("无效的任务 ID。")
    run_dir = (output_root / raw_run_id).resolve()
    try:
        run_dir.relative_to(output_root.resolve())
    except ValueError as exc:
        raise ValueError("无效的任务 ID。") from exc
    return run_dir / "results"


def parse_bool(raw_value: str, default: bool = False) -> bool:
    value = (raw_value or "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def options_from_form(form: MultiDict[str, str]) -> ProcessOptions:
    processing_mode = rmbg_onnx.normalize_processing_mode(
        form.get("processingMode", "rmbg")
    )
    output_format = rmbg_onnx.normalize_output_format(form.get("outputFormat", "png"))
    edge_optimize = parse_bool(form.get("edgeOptimize", "false"), default=False)
    transparent_background = parse_bool(
        form.get("transparentBackground", "true"),
        default=True,
    )
    background_color = form.get("backgroundColor", "#FFFFFF") or "#FFFFFF"
    rmbg_onnx.normalize_background_color(background_color)
    return ProcessOptions(
        processing_mode=processing_mode,
        output_format=output_format,
        edge_optimize=edge_optimize,
        transparent_background=transparent_background,
        background_color=background_color,
    )


def process_item(
    field: FileStorage,
    relative_name: str,
    fallback_name: str,
    input_dir: Path,
    result_dir: Path,
    run_id: str,
    session: rmbg_onnx.RmbgSession,
    options: ProcessOptions | None = None,
) -> tuple[dict[str, object], bool]:
    options = options or ProcessOptions()
    relative_path = safe_relative_path(relative_name, fallback_name)
    relative_posix = relative_path.as_posix()
    item: dict[str, object] = {
        "inputName": relative_posix,
        "inputUrl": f"/outputs/{quote(run_id)}/_uploads/{quote(relative_posix, safe='/')}",
        "ok": False,
        "message": "",
        "outputName": "",
        "outputPath": "",
        "outputUrl": "",
        "seconds": 0.0,
    }

    stage = "输入校验"
    try:
        if not is_supported_image(relative_path):
            raise ValueError("不支持的文件格式")

        stage = "保存上传文件"
        source_path = input_dir / relative_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        field.save(source_path)

        stage = "模型处理"
        target_path = result_dir / output_name(
            relative_path,
            options.output_format,
            options.processing_mode,
        )
        started_at = time.perf_counter()
        run_result = session.remove_background(
            input_path=source_path,
            output_path=target_path,
            processing_mode=options.processing_mode,
            output_format=options.output_format,
            edge_optimize=options.edge_optimize,
            transparent_background=options.transparent_background,
            background_color=options.background_color,
        )
        seconds = time.perf_counter() - started_at
        item.update(
            {
                "ok": True,
                "message": "完成",
                "outputName": target_path.name,
                "outputPath": str(target_path),
                "outputUrl": (
                    f"/outputs/{quote(run_id)}/results/"
                    f"{quote(target_path.relative_to(result_dir).as_posix(), safe='/')}"
                ),
                "seconds": round(seconds, 3),
                "inferenceSeconds": round(run_result.inference_seconds, 3),
                "outputFormat": options.output_format,
                "processingMode": options.processing_mode,
                "transparentBackground": options.transparent_background,
            }
        )
        return item, True
    except Exception as exc:
        error_specs = {
            "输入校验": (
                "UNSUPPORTED_INPUT",
                "输入文件未通过校验。",
                "请选择 JPG、PNG、WEBP、静态 AVIF、BMP、单页 TIFF、ICO 或 TGA 图片。",
            ),
            "保存上传文件": (
                "UPLOAD_SAVE_FAILED",
                "无法保存上传的图片。",
                "请重新选择图片；若持续失败，请检查磁盘剩余空间。",
            ),
            "模型处理": (
                "INFERENCE_FAILED",
                "模型未能完成这张图片的处理。",
                "请先重试；若持续失败，请切换 CPU 推理或检查模型文件是否完整。",
            ),
        }
        code, reason, suggestion = error_specs[stage]
        detail = " ".join(str(exc).split()) or "未提供具体错误信息"
        item["message"] = reason
        item["error"] = {
            "code": code,
            "stage": stage,
            "reason": reason,
            "detail": f"{type(exc).__name__}: {detail[:500]}",
            "suggestion": suggestion,
        }
        traceback.print_exc()
        return item, False


def iter_process_events(
    fields: list[FileStorage],
    relative_paths: list[str],
    output_root: Path,
    session: rmbg_onnx.RmbgSession,
    run_id: str | None = None,
    options: ProcessOptions | None = None,
) -> Iterator[dict[str, object]]:
    options = options or ProcessOptions()
    output_root.mkdir(parents=True, exist_ok=True)
    if run_id:
        started = run_id
        run_dir = output_root / started
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        while True:
            started = new_run_id()
            run_dir = output_root / started
            try:
                run_dir.mkdir(exist_ok=False)
                break
            except FileExistsError:
                continue
    input_dir = run_dir / "_uploads"
    result_dir = run_dir / "results"
    input_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)

    total = len(fields)
    results: list[dict[str, object]] = []
    success_count = 0
    created_at = now_text()
    manifest: dict[str, object] = {
        "schemaVersion": 1,
        "runId": started,
        "createdAt": created_at,
        "updatedAt": created_at,
        "status": "running",
        "total": total,
        "success": 0,
        "failed": 0,
        "runDir": str(run_dir),
        "outputDir": str(result_dir),
        "options": process_options_payload(options),
        "items": results,
    }
    write_task_manifest(run_dir, manifest)
    yield {
        "type": "start",
        "total": total,
        "success": 0,
        "failed": 0,
        "runId": started,
        "outputDir": str(result_dir),
    }

    for index, field in enumerate(fields, start=1):
        file_name = field.filename or f"image-{index}.png"
        relative_name = (
            relative_paths[index - 1]
            if index - 1 < len(relative_paths) and relative_paths[index - 1]
            else file_name
        )
        item, ok = process_item(
            field=field,
            relative_name=relative_name,
            fallback_name=file_name,
            input_dir=input_dir,
            result_dir=result_dir,
            run_id=started,
            session=session,
            options=options,
        )
        if ok:
            success_count += 1
        results.append(item)
        manifest.update(
            {
                "success": success_count,
                "failed": len(results) - success_count,
                "items": results,
            }
        )
        write_task_manifest(run_dir, manifest)
        yield {
            "type": "item",
            "index": index,
            "total": total,
            "success": success_count,
            "failed": len(results) - success_count,
            "runId": started,
            "outputDir": str(result_dir),
            "item": item,
        }

    manifest.update(
        {
            "status": "done",
            "total": len(results),
            "success": success_count,
            "failed": len(results) - success_count,
            "items": results,
        }
    )
    write_task_manifest(run_dir, manifest)
    yield {
        "type": "done",
        "ok": success_count > 0,
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "runId": started,
        "outputDir": str(result_dir),
        "items": results,
        "options": process_options_payload(options),
    }
