from __future__ import annotations

import argparse
import json
import platform
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import rmbg_onnx
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from task_service import iter_process_events, load_recent_tasks, options_from_form
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

    @app.get("/outputs/<path:name>")
    def output_file(name: str):
        return send_from_directory(state.output_root, name)

    @app.get("/<path:name>")
    def static_asset(name: str):
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
    origin = f"http://{args.host}:{args.port}"
    try:
        state = load_state(args, server_origin=origin)
    except Exception as exc:
        print("")
        print("Failed to load the model or execution provider.")
        print(str(exc))
        return 1

    app = create_app(state, max_upload_mb=args.max_upload_mb)
    print(f"Server ready: {origin}/")
    print("Close this window to release the model session.")
    if args.open:
        webbrowser.open(f"{origin}/")
    serve(app, host=args.host, port=args.port, threads=4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
