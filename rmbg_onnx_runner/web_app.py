from __future__ import annotations

import argparse
import json
import platform
import secrets
import threading
from dataclasses import dataclass
from pathlib import Path

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
from runtime import (
    find_available_port,
    open_in_file_manager,
    open_web_page,
    require_loopback,
)
from task_service import (
    iter_process_events,
    load_recent_tasks,
    options_from_form,
    result_dir_for_run,
)
from waitress import serve
from werkzeug.exceptions import RequestEntityTooLarge

ROOT_DIR = Path(__file__).resolve().parent.parent
RUNNER_DIR = Path(__file__).resolve().parent
WEB_DIR = RUNNER_DIR / "web"
DEFAULT_MODEL = ROOT_DIR / "model.onnx"
DEFAULT_OUTPUTS = ROOT_DIR / "outputs"
SERVER_VERSION = "0.1.0"


@dataclass
class WebAppState:
    model_path: Path
    output_root: Path
    provider: str
    session: rmbg_onnx.RmbgSession
    access_token: str
    server_origin: str


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

    @app.post("/api/process")
    def process():
        fields = request.files.getlist("files")
        if not fields:
            return jsonify(error="请上传图片文件。"), 400
        try:
            options = options_from_form(request.form)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

        events = iter_process_events(
            fields=fields,
            relative_paths=request.form.getlist("paths"),
            output_root=state.output_root,
            session=state.session,
            options=options,
        )
        if "application/x-ndjson" in request.headers.get("Accept", "").lower():

            def lines():
                for event in events:
                    yield json.dumps(event, ensure_ascii=False) + "\n"

            return Response(
                stream_with_context(lines()),
                content_type="application/x-ndjson; charset=utf-8",
            )

        final_event = None
        for event in events:
            if event["type"] == "done":
                final_event = event
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

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return jsonify(error=f"上传内容超过 {max_upload_mb} MB 限制。"), 413

    return app


def load_state(
    args: argparse.Namespace,
    access_token: str = "",
    server_origin: str = "",
) -> WebAppState:
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
        access_token=access_token,
        server_origin=server_origin,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the local RMBG Flask UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUTS))
    parser.add_argument("--provider", choices=["cuda", "auto", "cpu"], default="cuda")
    parser.add_argument("--strict-provider", action="store_true")
    parser.add_argument("--max-upload-mb", type=int, default=1024)
    parser.add_argument("--open", action="store_true", help="Open the browser after loading the model.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
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
    print(f"Server ready: {origin}/")
    print("The access token is embedded in the opened local URL.")
    if args.open:
        threading.Timer(0.5, open_web_page, args=(f"{origin}/?token={token}",)).start()
    serve(app, host=host, port=port, threads=4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
