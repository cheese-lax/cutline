from __future__ import annotations

import json
import time
import traceback
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterator
from urllib.parse import quote

import rmbg_onnx
from werkzeug.datastructures import FileStorage, MultiDict

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class ProcessOptions:
    processing_mode: str = "rmbg"
    output_format: str = "png"
    edge_optimize: bool = False
    transparent_background: bool = True
    background_color: str = "#FFFFFF"


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

    try:
        if not is_supported_image(relative_path):
            raise ValueError("不支持的文件格式")

        source_path = input_dir / relative_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        field.save(source_path)

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
        item["message"] = str(exc)
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
    started = run_id or time.strftime("%Y%m%d-%H%M%S")
    run_dir = output_root / started
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
