from __future__ import annotations

import argparse
import cgi
import json
import mimetypes
import os
import shutil
import subprocess
import time
import traceback
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs
from urllib.parse import quote
from urllib.parse import unquote, urlparse

import rmbg_onnx


ROOT_DIR = Path(__file__).resolve().parent.parent
RUNNER_DIR = Path(__file__).resolve().parent
WEB_DIR = RUNNER_DIR / "web"
DEFAULT_MODEL = ROOT_DIR / "model.onnx"
DEFAULT_OUTPUTS = ROOT_DIR / "outputs"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
MANIFEST_NAME = "manifest.json"


@dataclass
class WebAppState:
    model_path: Path
    output_root: Path
    provider: str
    session: rmbg_onnx.RmbgSession


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
    return relative_path.with_name(f"{stem}_{suffix}.{rmbg_onnx.normalize_output_format(output_format)}")


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


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
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


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
    if "/" in raw_run_id or "\\" in raw_run_id or raw_run_id in {".", ".."} or raw_run_id.endswith(":"):
        raise ValueError("无效的任务 ID。")
    run_dir = (output_root / raw_run_id).resolve()
    try:
        run_dir.relative_to(output_root.resolve())
    except ValueError as exc:
        raise ValueError("无效的任务 ID。") from exc
    return run_dir / "results"


def form_fields(form: cgi.FieldStorage, name: str) -> list[object]:
    if name not in form:
        return []
    fields = form[name]
    if isinstance(fields, list):
        return fields
    return [fields]


def form_value(form: cgi.FieldStorage, name: str, default: str = "") -> str:
    fields = form_fields(form, name)
    if not fields:
        return default
    return str(getattr(fields[0], "value", default))


def parse_bool(raw_value: str, default: bool = False) -> bool:
    value = (raw_value or "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def process_options_from_form(form: cgi.FieldStorage) -> ProcessOptions:
    processing_mode = rmbg_onnx.normalize_processing_mode(form_value(form, "processingMode", "rmbg"))
    output_format = rmbg_onnx.normalize_output_format(form_value(form, "outputFormat", "png"))
    edge_optimize = parse_bool(form_value(form, "edgeOptimize", "false"), default=False)
    transparent_background = parse_bool(form_value(form, "transparentBackground", "true"), default=True)
    background_color = form_value(form, "backgroundColor", "#FFFFFF") or "#FFFFFF"
    rmbg_onnx.normalize_background_color(background_color)
    return ProcessOptions(
        processing_mode=processing_mode,
        output_format=output_format,
        edge_optimize=edge_optimize,
        transparent_background=transparent_background,
        background_color=background_color,
    )


def process_item(
    field: object,
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
        with source_path.open("wb") as output_file:
            shutil.copyfileobj(field.file, output_file)

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
    fields: list[object],
    relative_paths: list[str],
    output_root: Path,
    session: rmbg_onnx.RmbgSession,
    run_id: str | None = None,
    options: ProcessOptions | None = None,
):
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
        file_name = getattr(field, "filename", "") or f"image-{index}.png"
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


class RmbgWebHandler(BaseHTTPRequestHandler):
    server_version = "RMBGWeb/1.0"

    @property
    def state(self) -> WebAppState:
        return self.server.state  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def accepts_stream(self) -> bool:
        return "application/x-ndjson" in self.headers.get("Accept", "").lower()

    def send_ndjson_events(self, events) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        for event in events:
            self.wfile.write(json_bytes(event) + b"\n")
            self.wfile.flush()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/api/status":
            self.handle_status()
            return
        if path == "/api/open-output":
            self.handle_open_output(parsed)
            return
        if path == "/api/open-result":
            self.handle_open_result(parsed)
            return
        if path == "/api/tasks/recent":
            self.handle_recent_tasks(parsed)
            return
        if path.startswith("/outputs/"):
            self.serve_output(path)
            return
        self.serve_static(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/process":
            self.handle_process()
            return
        self.send_text("Not found", HTTPStatus.NOT_FOUND)

    def serve_static(self, request_path: str) -> None:
        if request_path in {"", "/"}:
            file_path = WEB_DIR / "index.html"
        else:
            relative = request_path.lstrip("/")
            file_path = (WEB_DIR / relative).resolve()
            if WEB_DIR.resolve() not in file_path.parents:
                self.send_text("Not found", HTTPStatus.NOT_FOUND)
                return

        if not file_path.is_file():
            self.send_text("Not found", HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_output(self, request_path: str) -> None:
        relative = request_path.removeprefix("/outputs/").replace("/", os.sep)
        file_path = (self.state.output_root / relative).resolve()
        try:
            file_path.relative_to(self.state.output_root.resolve())
        except ValueError:
            self.send_text("Not found", HTTPStatus.NOT_FOUND)
            return

        if not file_path.is_file():
            self.send_text("Not found", HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_status(self) -> None:
        self.send_json(
            {
                "ready": True,
                "model": str(self.state.model_path),
                "outputs": str(self.state.output_root),
                "providerRequested": [str(item) for item in self.state.session.provider_requested],
                "providerActive": self.state.session.provider_active,
                "loadSeconds": round(self.state.session.load_seconds, 3),
                "inputShape": list(self.state.session.model_input.shape),
                "inputType": self.state.session.model_input.type,
            }
        )

    def handle_open_output(self, parsed) -> None:
        query = parse_qs(parsed.query)
        run_id = query.get("runId", [""])[0]
        self.state.output_root.mkdir(parents=True, exist_ok=True)
        try:
            target = result_dir_for_run(self.state.output_root, run_id)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if not target.exists() and run_id:
            self.send_json({"error": "任务结果目录不存在。"}, HTTPStatus.NOT_FOUND)
            return

        target.mkdir(parents=True, exist_ok=True)
        open_in_file_manager(target)
        self.send_json({"ok": True, "path": str(target)})

    def handle_recent_tasks(self, parsed) -> None:
        query = parse_qs(parsed.query)
        try:
            limit = int(query.get("limit", ["10"])[0])
        except ValueError:
            limit = 10
        tasks = load_recent_tasks(self.state.output_root, limit=max(1, min(limit, 50)))
        self.send_json({"tasks": tasks, "latest": tasks[0] if tasks else None})

    def handle_open_result(self, parsed) -> None:
        query = parse_qs(parsed.query)
        raw_path = query.get("path", [""])[0]
        if not raw_path:
            self.send_json({"error": "缺少结果图片路径。"}, HTTPStatus.BAD_REQUEST)
            return

        file_path = Path(raw_path).resolve()
        try:
            file_path.relative_to(self.state.output_root.resolve())
        except ValueError:
            self.send_json({"error": "只能打开结果目录内的图片。"}, HTTPStatus.BAD_REQUEST)
            return

        if not file_path.is_file():
            self.send_json({"error": "结果图片不存在。"}, HTTPStatus.NOT_FOUND)
            return

        open_in_file_manager(file_path)
        self.send_json({"ok": True, "path": str(file_path)})

    def handle_process(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self.send_json({"error": "请上传图片文件。"}, HTTPStatus.BAD_REQUEST)
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )

        fields = form_fields(form, "files")
        path_fields = form_fields(form, "paths")
        relative_paths = [unquote(getattr(path_field, "value", "")) for path_field in path_fields]
        try:
            options = process_options_from_form(form)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        events = iter_process_events(
            fields=fields,
            relative_paths=relative_paths,
            output_root=self.state.output_root,
            session=self.state.session,
            options=options,
        )
        if self.accepts_stream():
            self.send_ndjson_events(events)
            return

        final_event = None
        for event in events:
            if event.get("type") == "done":
                final_event = event
        if final_event is None:
            self.send_json({"error": "处理失败，未生成结果。"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        payload = dict(final_event)
        payload.pop("type", None)
        self.send_json(payload)


def open_in_file_manager(path: Path) -> None:
    path = path.resolve()
    if os.name == "nt":
        if path.is_file():
            subprocess.Popen(["explorer", f"/select,{path}"])
        else:
            subprocess.Popen(["explorer", str(path)])
    else:
        target = path.parent if path.is_file() else path
        webbrowser.open(target.as_uri())


def open_web_page(url: str) -> None:
    if os.name == "nt":
        subprocess.Popen(["cmd", "/c", "start", "", url])
    else:
        webbrowser.open(url)


class RmbgThreadingHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, state: WebAppState):
        super().__init__(server_address, handler_class)
        self.state = state


def load_state(args: argparse.Namespace) -> WebAppState:
    model_path = Path(args.model).resolve()
    output_root = Path(args.output_dir).resolve()
    print(f"Loading model: {model_path}")
    session = rmbg_onnx.RmbgSession(
        model_path=model_path,
        provider=args.provider,
        disable_fallback=args.strict_provider,
    )
    print(f"Model loaded in {session.load_seconds:.3f}s")
    print(f"Active providers: {session.provider_active}")
    output_root.mkdir(parents=True, exist_ok=True)
    return WebAppState(
        model_path=model_path,
        output_root=output_root,
        provider=args.provider,
        session=session,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the local RMBG web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUTS))
    parser.add_argument("--provider", choices=["cuda", "auto", "cpu"], default="cuda")
    parser.add_argument("--strict-provider", action="store_true")
    parser.add_argument("--open", action="store_true", help="Open the browser after the model is loaded.")
    args = parser.parse_args()

    try:
        state = load_state(args)
    except Exception as exc:
        print("")
        print("Failed to load the model or CUDA provider.")
        print(str(exc))
        return 1

    address = (args.host, args.port)
    httpd = RmbgThreadingHTTPServer(address, RmbgWebHandler, state)
    url = f"http://{args.host}:{args.port}/"
    print(f"Server ready: {url}")
    print("Close this window to release the model session.")
    if args.open:
        open_web_page(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Stopping server...")
    finally:
        httpd.server_close()
        state.session = None  # type: ignore[assignment]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
