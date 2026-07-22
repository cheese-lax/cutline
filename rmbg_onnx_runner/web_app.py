from __future__ import annotations

import argparse
import json
import platform
import secrets
import threading
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from tempfile import SpooledTemporaryFile

import rmbg_onnx
from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    request,
    send_from_directory,
    stream_with_context,
)
from model_manager import ModelManager, RuntimeBusyError, RuntimeLoadError, RuntimeSelection, provider_catalog
from runtime import (
    find_available_port,
    open_in_file_manager,
    open_web_page,
    require_loopback,
)
from runtime_preferences import load_last_model, save_last_model
from task_service import (
    cleanup_task_history,
    delete_task_history,
    iter_process_events,
    list_task_history,
    load_recent_tasks,
    load_task_for_run,
    options_from_form,
    result_dir_for_run,
    task_history_summary,
)
from waitress import serve
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import RequestEntityTooLarge

ROOT_DIR = Path(__file__).resolve().parent.parent
RUNNER_DIR = Path(__file__).resolve().parent
WEB_DIR = RUNNER_DIR / "web"
MODELS_DIR = ROOT_DIR / "models"
DEFAULT_OUTPUTS = ROOT_DIR / "outputs"
SERVER_VERSION = "0.3.0"
UPLOAD_SPOOL_MEMORY_BYTES = 8 * 1024 * 1024


@dataclass
class WebAppState:
    model_path: Path | None
    output_root: Path
    provider: str
    session: rmbg_onnx.RmbgSession | None
    access_token: str
    server_origin: str
    models_dir: Path = MODELS_DIR
    disable_fallback: bool = False
    model_lock: threading.Lock = dataclass_field(default_factory=threading.Lock)
    history_retention_days: int = 30
    history_max_tasks: int = 100
    history_keep_latest: int = 10
    runtime: ModelManager | None = None
    disable_mem_pattern: bool = False


def model_id(models_dir: Path, model_path: Path) -> str:
    try:
        return model_path.resolve().relative_to(models_dir.resolve()).as_posix()
    except ValueError:
        return ""


def discover_models(models_dir: Path) -> list[dict[str, object]]:
    root = models_dir.resolve()
    if not root.is_dir():
        return []
    models = []
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".onnx":
            continue
        identifier = model_id(root, path)
        if not identifier:
            continue
        try:
            size_bytes = path.stat().st_size
        except OSError:
            continue
        models.append(
            {
                "id": identifier,
                "name": path.name,
                "sizeBytes": size_bytes,
            }
        )
    models.sort(key=lambda item: str(item["id"]).casefold())
    return models


def resolve_model(models_dir: Path, identifier: str) -> Path:
    raw_identifier = (identifier or "").strip()
    if not raw_identifier:
        raise ValueError("请选择 models 文件夹中的 ONNX 模型。")
    root = models_dir.resolve()
    candidate = (root / raw_identifier).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("只能选择 models 文件夹中的 ONNX 模型。") from exc
    if (
        candidate.suffix.lower() != ".onnx"
        or not candidate.is_file()
        or (root / raw_identifier).is_symlink()
    ):
        raise ValueError("所选模型不存在或不是可用的 ONNX 文件。")
    return candidate


def choose_startup_model(models_dir: Path, requested: str, saved: str) -> Path | None:
    if requested:
        return resolve_model(models_dir, requested)
    if saved:
        try:
            return resolve_model(models_dir, saved)
        except ValueError:
            print(f"Saved model is unavailable, falling back: {saved}")
    models = discover_models(models_dir)
    return resolve_model(models_dir, str(models[0]["id"])) if models else None


def detach_uploads(fields: list[FileStorage]) -> list[FileStorage]:
    """Copy request-owned uploads into streams that outlive the Flask request."""
    detached: list[FileStorage] = []
    active_stream = None
    try:
        for field in fields:
            active_stream = SpooledTemporaryFile(
                max_size=UPLOAD_SPOOL_MEMORY_BYTES,
                mode="w+b",
            )
            field.save(active_stream)
            active_stream.seek(0)
            detached.append(
                FileStorage(
                    stream=active_stream,
                    filename=field.filename,
                    name=field.name,
                    content_type=field.content_type,
                    headers=field.headers,
                )
            )
            active_stream = None
    except Exception:
        if active_stream is not None:
            active_stream.close()
        close_uploads(detached)
        raise
    return detached


def close_uploads(fields: list[FileStorage]) -> None:
    for field in fields:
        field.close()


def error_detail(exc: Exception) -> str:
    message = " ".join(str(exc).split()) or "未提供具体错误信息"
    return f"{type(exc).__name__}: {message[:500]}"


def create_app(state: WebAppState, max_upload_mb: int = 1024) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = max_upload_mb * 1024 * 1024
    app.extensions["rmbg_state"] = state

    def valid_host() -> bool:
        return (
            request.host == "127.0.0.1"
            or request.host.startswith("127.0.0.1:")
            or request.host == "localhost"
            or request.host.startswith("localhost:")
        )

    @app.before_request
    def protect_local_service():
        if not valid_host():
            abort(403)
        supplied = request.cookies.get("koutu_access", "")
        if request.path == "/":
            supplied = request.args.get("token", "") or supplied
        if not secrets.compare_digest(supplied, state.access_token):
            abort(403)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("Origin")
            if origin and origin != state.server_origin:
                abort(403)

    @app.after_request
    def secure_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob: data:; "
            "style-src 'self'; script-src 'self'; connect-src 'self'"
        )
        return response

    @app.get("/")
    def index():
        response = send_from_directory(WEB_DIR, "index.html")
        response.set_cookie(
            "koutu_access",
            state.access_token,
            httponly=True,
            samesite="Strict",
            path="/",
        )
        return response

    @app.get("/api/status")
    def status():
        if state.runtime is not None:
            payload = state.runtime.status()
            payload.update(
                outputs=str(state.output_root),
                modelsDir=str(state.models_dir.resolve()),
                platform=platform.system(),
                serverVersion=SERVER_VERSION,
            )
            return jsonify(payload)
        return jsonify(
            ready=True,
            model=str(state.model_path),
            outputs=str(state.output_root),
            providerRequested=[str(item) for item in state.session.provider_requested],
            providerActive=state.session.provider_active,
            loadSeconds=round(state.session.load_seconds, 3),
            inputShape=list(state.session.model_input.shape),
            inputType=state.session.model_input.type,
            platform=platform.system(),
            serverVersion=SERVER_VERSION,
        )

    @app.get("/api/models")
    def models():
        return jsonify(
            models=discover_models(state.models_dir),
            active=model_id(state.models_dir, state.model_path) if state.model_path else None,
        )

    @app.get("/api/providers")
    def providers():
        available = []
        try:
            import onnxruntime as ort

            available = ort.get_available_providers()
        except ImportError:
            available = ["CPUExecutionProvider"]
        selected = state.runtime.status()["provider"] if state.runtime else state.provider
        return jsonify(selected=selected, providers=provider_catalog(available, platform.system()))

    @app.post("/api/runtime/select")
    def select_runtime():
        if state.runtime is None:
            return jsonify(error="运行时管理器不可用。"), 503
        payload = request.get_json(silent=True) or {}
        try:
            selected_path = resolve_model(state.models_dir, str(payload.get("model") or ""))
            selection = RuntimeSelection(
                model_id=model_id(state.models_dir, selected_path),
                model_path=selected_path,
                provider=str(payload.get("provider") or "auto"),
                disable_fallback=state.disable_fallback,
                disable_mem_pattern=state.disable_mem_pattern,
            )
            state.runtime.switch(selection)
            state.model_path = selected_path
            state.provider = selection.provider
            save_last_model(state.output_root / ".runtime-state.json", selection.model_id)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except RuntimeBusyError as exc:
            return jsonify(error=str(exc)), 409
        except RuntimeLoadError as exc:
            response = {"error": str(exc), **exc.detail}
            if exc.restored_model:
                response["restoredModel"] = exc.restored_model
            return jsonify(response), 400
        metadata = state.runtime.status()
        return jsonify(ok=True, active=selection.model_id, provider=selection.provider, providerActive=metadata["providerActive"], loadSeconds=metadata["loadSeconds"])

    @app.post("/api/models/select")
    def select_model():
        payload = request.get_json(silent=True) or {}
        try:
            selected_path = resolve_model(
                state.models_dir,
                str(payload.get("model") or ""),
            )
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

        with state.model_lock:
            if selected_path != state.model_path.resolve():
                try:
                    replacement = rmbg_onnx.RmbgSession(
                        model_path=selected_path,
                        provider=state.provider,
                        disable_fallback=state.disable_fallback,
                    )
                except Exception as exc:
                    return (
                        jsonify(
                            error="模型加载失败，已继续使用当前模型。",
                            detail=error_detail(exc),
                        ),
                        400,
                    )
                state.session = replacement
                state.model_path = selected_path

        return jsonify(
            ok=True,
            active=model_id(state.models_dir, state.model_path),
            providerActive=state.session.provider_active,
            loadSeconds=round(state.session.load_seconds, 3),
        )

    @app.post("/api/process")
    def process():
        fields = request.files.getlist("files")
        if not fields:
            return jsonify(error="请上传图片文件。"), 400
        try:
            options = options_from_form(request.form)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

        relative_paths = request.form.getlist("paths")
        try:
            detached_fields = detach_uploads(fields)
        except Exception as exc:
            return (
                jsonify(
                    error="无法暂存上传文件。",
                    detail=error_detail(exc),
                    suggestion="请重新选择图片；若持续失败，请检查磁盘剩余空间。",
                ),
                500,
            )

        lease = None
        try:
            if state.runtime is not None:
                lease = state.runtime.acquire()
                session = lease.session
            elif state.session is not None:
                session = state.session
            else:
                return jsonify(error="尚未加载可用模型。"), 503
            events = iter_process_events(fields=detached_fields, relative_paths=relative_paths, output_root=state.output_root, session=session, options=options)
        except RuntimeBusyError as exc:
            close_uploads(detached_fields)
            return jsonify(error=str(exc)), 409
        if "application/x-ndjson" in request.headers.get("Accept", "").lower():

            def lines():
                try:
                    for event in events:
                        yield json.dumps(event, ensure_ascii=False) + "\n"
                finally:
                    close_uploads(detached_fields)
                    if lease:
                        lease.close()

            return Response(
                stream_with_context(lines()),
                content_type="application/x-ndjson; charset=utf-8",
            )

        final_event = None
        try:
            for event in events:
                if event["type"] == "done":
                    final_event = event
        finally:
            close_uploads(detached_fields)
            if lease:
                lease.close()
        if final_event is None:
            return jsonify(error="处理失败，未生成结果。"), 500
        payload = dict(final_event)
        payload.pop("type", None)
        return jsonify(payload)

    @app.get("/api/tasks/recent")
    def recent_tasks():
        try:
            limit = int(request.args.get("limit", "10"))
        except ValueError:
            limit = 10
        tasks = load_recent_tasks(state.output_root, limit=max(1, min(limit, 50)))
        return jsonify(tasks=tasks, latest=tasks[0] if tasks else None)

    @app.get("/api/tasks/history")
    def history_summary():
        protect_run_id = request.args.get("protectRunId", "").strip()
        quick_days = request.args.get("olderThanDays", "").strip()
        if quick_days:
            try:
                retention_days = int(quick_days)
            except ValueError:
                retention_days = -1
            if retention_days not in {7, 30}:
                return jsonify(error="一键清理仅支持 7 天或 30 天。"), 400
            max_tasks = 0
            keep_latest = 0
        else:
            retention_days = state.history_retention_days
            max_tasks = state.history_max_tasks
            keep_latest = state.history_keep_latest
        protected = {protect_run_id} if protect_run_id else set()
        summary = task_history_summary(
            state.output_root,
            retention_days=retention_days,
            max_tasks=max_tasks,
            keep_latest=keep_latest,
            protected_run_ids=protected,
        )
        summary["tasks"] = list_task_history(
            state.output_root,
            protected_run_ids=protected,
            limit=100,
        )
        return jsonify(summary)

    @app.get("/api/tasks/<run_id>")
    def task_detail(run_id: str):
        task = load_task_for_run(state.output_root, run_id)
        if task is None:
            return jsonify(error="任务不存在或任务 ID 无效。"), 404
        return jsonify(task=task)

    @app.post("/api/tasks/delete")
    def delete_tasks():
        payload = request.get_json(silent=True) or {}
        if payload.get("confirm") is not True:
            return jsonify(error="删除历史任务前必须明确确认。"), 400
        run_ids = payload.get("runIds")
        if not isinstance(run_ids, list) or not run_ids:
            return jsonify(error="请选择要删除的历史任务。"), 400
        if len(run_ids) > 100:
            return jsonify(error="一次最多删除 100 个历史任务。"), 400
        protect_run_id = str(payload.get("protectRunId") or "").strip()
        result = delete_task_history(
            state.output_root,
            [str(run_id) for run_id in run_ids],
            protected_run_ids={protect_run_id} if protect_run_id else set(),
        )
        return jsonify(result)

    @app.post("/api/tasks/cleanup")
    def cleanup_history():
        payload = request.get_json(silent=True) or {}
        if payload.get("confirm") is not True:
            return jsonify(error="清理历史结果前必须明确确认。"), 400
        quick_days = payload.get("olderThanDays")
        if quick_days is not None:
            try:
                retention_days = int(quick_days)
            except (TypeError, ValueError):
                retention_days = -1
            if retention_days not in {7, 30}:
                return jsonify(error="一键清理仅支持 7 天或 30 天。"), 400
            max_tasks = 0
            keep_latest = 0
        else:
            retention_days = state.history_retention_days
            max_tasks = state.history_max_tasks
            keep_latest = state.history_keep_latest
        protect_run_id = str(payload.get("protectRunId") or "").strip()
        result = cleanup_task_history(
            state.output_root,
            retention_days=retention_days,
            max_tasks=max_tasks,
            keep_latest=keep_latest,
            protected_run_ids={protect_run_id} if protect_run_id else set(),
        )
        return jsonify(result)

    @app.post("/api/open-output")
    def open_output():
        run_id = (request.get_json(silent=True) or {}).get("runId", "")
        try:
            target = result_dir_for_run(state.output_root, str(run_id))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        if run_id and not target.exists():
            return jsonify(error="任务结果目录不存在。"), 404
        target.mkdir(parents=True, exist_ok=True)
        target = target.resolve()
        open_in_file_manager(target)
        return jsonify(ok=True, path=str(target))

    @app.post("/api/open-result")
    def open_result():
        raw_path = (request.get_json(silent=True) or {}).get("path", "")
        if not raw_path:
            return jsonify(error="缺少结果图片路径。"), 400
        file_path = Path(str(raw_path)).resolve()
        try:
            file_path.relative_to(state.output_root.resolve())
        except ValueError:
            return jsonify(error="只能打开结果目录内的图片。"), 400
        if not file_path.is_file():
            return jsonify(error="结果图片不存在。"), 404
        open_in_file_manager(file_path)
        return jsonify(ok=True, path=str(file_path))

    @app.get("/outputs/<path:name>")
    def output_file(name: str):
        return send_from_directory(state.output_root, name)

    @app.get("/style.css")
    @app.get("/app.js")
    def static_asset():
        name = request.path.removeprefix("/")
        return send_from_directory(WEB_DIR, name)

    @app.get("/cutline-logo.png")
    def cutline_logo():
        return send_from_directory(WEB_DIR, "cutline-logo.png")

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return jsonify(error=f"上传内容超过 {max_upload_mb} MB 限制。"), 413

    return app


def load_state(
    args: argparse.Namespace,
    access_token: str = "",
    server_origin: str = "",
) -> WebAppState:
    models_dir = Path(args.models_dir).resolve()
    output_root = Path(args.output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    requested = args.model or ""
    if requested:
        requested_path = Path(requested)
        if requested_path.is_absolute() or requested_path.exists():
            requested = model_id(models_dir, requested_path.resolve())
        if not requested:
            raise ValueError("--model must point to an ONNX file inside the models directory.")
    model_path = choose_startup_model(models_dir, requested, load_last_model(output_root / ".runtime-state.json"))
    runtime = ModelManager()
    state = WebAppState(
        model_path=model_path,
        output_root=output_root,
        provider=args.provider,
        session=None,
        access_token=access_token,
        server_origin=server_origin,
        models_dir=models_dir,
        disable_fallback=args.strict_provider,
        history_retention_days=args.history_days,
        history_max_tasks=args.history_max_tasks,
        history_keep_latest=args.history_keep_latest,
        runtime=runtime,
        disable_mem_pattern=args.disable_mem_pattern,
    )
    if model_path is None:
        print(f"No ONNX model found. Put a model in: {models_dir}")
        print("Download: https://huggingface.co/briaai/RMBG-2.0/tree/main/onnx (check its license first)")
    else:
        selection = RuntimeSelection(model_id(models_dir, model_path), model_path, args.provider, args.strict_provider, args.disable_mem_pattern)

        def load_initial_model():
            try:
                runtime.start(selection)
                save_last_model(output_root / ".runtime-state.json", selection.model_id)
                print(f"Model ready: {selection.model_id}")
            except RuntimeLoadError as exc:
                print(f"Model load failed: {exc}")

        threading.Thread(target=load_initial_model, daemon=True).start()
    if args.auto_cleanup:
        cleanup_result = cleanup_task_history(
            output_root,
            retention_days=state.history_retention_days,
            max_tasks=state.history_max_tasks,
            keep_latest=state.history_keep_latest,
        )
        print(
            "History cleanup: "
            f"deleted {cleanup_result['deletedTasks']} task(s), "
            f"freed {cleanup_result['freedBytes']} byte(s)"
        )
    return state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the local RMBG Flask UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--models-dir", default=str(MODELS_DIR))
    parser.add_argument("--model", default=None)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUTS))
    parser.add_argument(
        "--provider",
        choices=["auto", "cuda", "coreml", "cpu"],
        default="auto",
    )
    parser.add_argument("--strict-provider", action="store_true")
    parser.add_argument("--disable-mem-pattern", action="store_true")
    parser.add_argument("--max-upload-mb", type=int, default=1024)
    parser.add_argument("--history-days", type=int, default=30)
    parser.add_argument("--history-max-tasks", type=int, default=100)
    parser.add_argument("--history-keep-latest", type=int, default=10)
    parser.add_argument("--auto-cleanup", action="store_true")
    parser.add_argument("--open", action="store_true", help="Open the browser after loading the model.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if min(args.history_days, args.history_max_tasks, args.history_keep_latest) < 0:
            raise ValueError("History retention options cannot be negative.")
        host = require_loopback(args.host)
        port = find_available_port(host, args.port)
        token = secrets.token_urlsafe(32)
        origin = f"http://{host}:{port}"
        state = load_state(
            args,
            access_token=token,
            server_origin=origin,
        )
    except Exception as exc:
        print("")
        print("Failed to load the model or execution provider.")
        print(str(exc))
        return 1

    app = create_app(state, max_upload_mb=args.max_upload_mb)
    print(f"Server ready: {origin}/?token={token}", flush=True)
    print("The access token is embedded in the opened local URL.", flush=True)
    if args.open:
        threading.Timer(0.5, open_web_page, args=(f"{origin}/?token={token}",)).start()
    serve(app, host=host, port=port, threads=4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
