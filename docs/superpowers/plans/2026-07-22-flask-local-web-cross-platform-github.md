# Flask Local Web Cross-Platform GitHub Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 RMBG-2.0 本地 Web Runner 改造成可在 Windows、macOS 和 Linux 从源码安装运行的 Flask 本地服务，保留现有浏览器 UI，并通过 GitHub 提供经过 CI 验证的源码版本。

**Architecture:** 保留 `rmbg_onnx.py` 作为推理内核，把任务清单、文件保存和批处理事件流抽到独立服务模块；用 Flask 应用工厂替换 `BaseHTTPRequestHandler`/`cgi.FieldStorage`，继续向前端输出 NDJSON 流。服务只监听回环地址，启动时生成访问令牌并写入 SameSite Cookie；各平台脚本创建本地虚拟环境、安装对应 ONNX Runtime、检查模型后打开浏览器。GitHub 只发布源码与发布说明，不包含模型权重、CUDA 运行库、用户数据或历史 ZIP。

**Tech Stack:** Python 3.11-3.13, Flask 3.x, Waitress 3.x, ONNX Runtime, NumPy, Pillow, HTML/CSS/vanilla JavaScript, pytest, GitHub Actions, PowerShell, POSIX shell

---

## 1. Scope, assumptions, and release gates

### Included

- Preserve the existing browser workflow, visual design, batch queue, NDJSON progress, recent-task recovery, line-art mode, PNG/WebP output, background options, and “open result folder” behavior.
- Replace the standard-library HTTP handler and removed `cgi` dependency with Flask/Werkzeug request parsing.
- Add local-only access-token protection, host checks, upload limits, safe output serving, and POST-only side-effect endpoints.
- Default provider selection to `auto`: CUDA first where available, CoreML first on macOS where available, then CPU.
- Provide install/start/check scripts for Windows, macOS, and Linux.
- Add dependency groups, test configuration, public repository documentation, code license, third-party notices, CI, and tag-driven GitHub source releases.

### Excluded from this plan

- Tauri/Electron/PyInstaller applications, DMG, MSI, NSIS, AppImage, code signing, notarization, app stores, and automatic binary updates.
- Bundling or automatically redistributing `model.onnx`.
- Exposing the service to LAN or the public internet.
- Multi-model selection. The new boundaries must make a later model registry possible, but this release keeps one RMBG model plus line-art mode.
- Changing the existing image-processing algorithm or redesigning the UI.

### Explicit assumptions

- Application source is released under MIT using `RMBG ONNX Runner contributors` as the copyright holder line.
- RMBG-2.0 weights remain a separately acquired, non-commercial dependency; the repository and GitHub Releases do not include the ONNX file.
- Supported source environments are Windows 10/11 x64, macOS 12+ on Apple Silicon or Intel, and current x64 Linux distributions with Python 3.11-3.13.
- CPU is the compatibility baseline. GPU acceleration is an optional capability, never a startup requirement.

### Release gates

- All unit and Flask integration tests pass on Windows, macOS, and Linux in GitHub Actions.
- A real-model smoke test passes manually on one Windows CUDA machine, one Apple Silicon Mac, and one CPU-only machine.
- A clean checkout can be installed and started using only the documented platform commands.
- The server refuses non-loopback binding, unauthenticated API calls, untrusted Host headers, and oversized requests.
- `git ls-files` contains no model, output image, virtual environment, secret, or historical update ZIP.

## 2. Target file map

### Repository-level files

- Create `README.md`: public landing page, quick start, supported platforms, model/license notice, security boundary, troubleshooting.
- Create `LICENSE`: MIT license for application source only.
- Create `THIRD_PARTY_NOTICES.md`: RMBG-2.0 and runtime dependency notices.
- Create `SECURITY.md`: vulnerability reporting and explicit localhost-only support statement.
- Create `pyproject.toml`: Python version, pytest, and Ruff configuration; the application remains source-run and is not published to PyPI.
- Modify `.gitignore`: exclude virtual environments, models, results, logs, local config, build artifacts, and historical ZIP exports.
- Create `requirements/base.txt`: Flask, Waitress, NumPy, Pillow.
- Create `requirements/cpu.txt`: base plus CPU ONNX Runtime.
- Create `requirements/windows-cuda.txt`: base plus CUDA-enabled ONNX Runtime and NVIDIA wheels.
- Create `requirements/macos.txt`: base plus macOS ONNX Runtime.
- Create `requirements/linux-cuda.txt`: base plus CUDA-enabled ONNX Runtime.
- Create `requirements/dev.txt`: CPU runtime plus pytest and Ruff.

### Application files

- Modify `rmbg_onnx_runner/rmbg_onnx.py`: portable provider selection and platform-aware DLL preload.
- Create `rmbg_onnx_runner/task_service.py`: processing options, safe relative paths, file persistence, NDJSON event source, manifest load/write.
- Create `rmbg_onnx_runner/runtime.py`: runtime configuration, access token, port selection, browser launch, and platform folder opening.
- Replace `rmbg_onnx_runner/web_app.py`: Flask application factory, protected routes, streaming response, CLI, Waitress startup.
- Modify `rmbg_onnx_runner/check_env.py`: portable provider diagnostics and meaningful exit codes.
- Modify `rmbg_onnx_runner/run_rmbg_onnx.py`: default to `auto` and expose `coreml` choice.
- Delete `rmbg_onnx_runner/requirements-win-gpu.txt` after the new requirement files are working.
- Delete `rmbg_onnx_runner/install_windows.ps1` after the root scripts are working.

### Browser files

- Modify `rmbg_onnx_runner/web/index.html`: replace fixed CUDA badge with dynamic provider text.
- Modify `rmbg_onnx_runner/web/app.js`: POST side-effect routes, JSON request bodies, clearer unauthorized/oversize errors.
- Keep `rmbg_onnx_runner/web/style.css` unchanged unless the dynamic provider badge needs an existing class reused.

### Platform scripts

- Create `scripts/install_windows.ps1` and `scripts/start_windows.ps1`.
- Create `scripts/install_macos.sh` and `scripts/start_macos.sh`.
- Create `scripts/install_linux.sh` and `scripts/start_linux.sh`.

### Tests and automation

- Modify `rmbg_onnx_runner/tests/test_rmbg_onnx.py`: provider matrix coverage.
- Replace `rmbg_onnx_runner/tests/test_web_app.py`: Flask test-client route, auth, streaming, limit, and path tests.
- Create `rmbg_onnx_runner/tests/test_task_service.py`: move current manifest and processing tests out of the HTTP layer.
- Modify `rmbg_onnx_runner/tests/test_web_assets.py`: dynamic provider and POST route assertions.
- Create `rmbg_onnx_runner/tests/test_runtime.py`: port, loopback, and platform-open behavior.
- Create `rmbg_onnx_runner/tests/test_repository.py`: repository hygiene and documentation contract.
- Create `.github/workflows/ci.yml`: three-OS CPU test matrix and script syntax checks.
- Create `.github/workflows/release-source.yml`: tag-triggered test gate and GitHub source release.

## 3. API compatibility contract

The frontend-visible response fields remain unchanged unless stated below.

| Route | Method | Behavior |
|---|---:|---|
| `/?token=<startup-token>` | GET | Validates token, sets `koutu_access` SameSite cookie, serves UI |
| `/style.css`, `/app.js` | GET | Serves static files only with valid cookie |
| `/api/status` | GET | Same JSON fields as today plus `platform` and `serverVersion` |
| `/api/process` | POST | Accepts multipart `files`, `paths`, and options; returns NDJSON when requested, otherwise final JSON |
| `/api/tasks/recent?limit=1` | GET | Same recent-task response |
| `/api/open-output` | POST | JSON body `{ "runId": "..." }`; opens only the selected run results directory |
| `/api/open-result` | POST | JSON body `{ "path": "..." }`; opens only a result under `output_root` |
| `/outputs/<path:name>` | GET | Serves only files located under `output_root` |

All routes except the initial tokenized `/` require the cookie. All requests require `Host` to be `127.0.0.1:<port>` or `localhost:<port>`. State-changing requests with an `Origin` header require it to match the local server origin.

## 4. Baseline evidence

- Current source is entirely untracked and the `main` branch has no commits. Historical ZIP files must never be staged implicitly.
- Current backend imports `cgi`, which is removed in Python 3.13.
- Current test command in this workspace fails before migration because the active test environment lacks NumPy/Pillow and `test_web_app.py` installs an incomplete `rmbg_onnx` stub. Establishing a reproducible dev environment is Task 1, not a Flask regression.
- Existing UI and processing tests are valuable contracts and should be moved or adapted, not discarded.

---

### Task 1: Establish reproducible dependencies and a clean test baseline

**Files:**
- Create: `pyproject.toml`
- Create: `requirements/base.txt`
- Create: `requirements/cpu.txt`
- Create: `requirements/windows-cuda.txt`
- Create: `requirements/macos.txt`
- Create: `requirements/linux-cuda.txt`
- Create: `requirements/dev.txt`
- Modify: `.gitignore`
- Modify: `rmbg_onnx_runner/tests/test_web_app.py:1-20`

- [ ] **Step 1: Create dependency groups**

Create the files with these exact dependency relationships:

```text
# requirements/base.txt
Flask>=3.1,<4
waitress>=3,<4
numpy>=2,<3
Pillow>=10,<13

# requirements/cpu.txt
-r base.txt
onnxruntime==1.26.0

# requirements/windows-cuda.txt
-r base.txt
onnxruntime-gpu[cuda,cudnn]==1.26.0

# requirements/macos.txt
-r base.txt
onnxruntime==1.26.0

# requirements/linux-cuda.txt
-r base.txt
onnxruntime-gpu[cuda,cudnn]==1.26.0

# requirements/dev.txt
-r cpu.txt
pytest>=8,<10
ruff>=0.12,<1
```

- [ ] **Step 2: Add Python tool configuration**

Create `pyproject.toml`:

```toml
[project]
name = "rmbg-onnx-runner"
version = "0.1.0"
description = "Local browser UI for ONNX background removal"
requires-python = ">=3.11,<3.14"

[tool.pytest.ini_options]
testpaths = ["rmbg_onnx_runner/tests"]
pythonpath = ["rmbg_onnx_runner"]
addopts = "-ra"

[tool.ruff]
target-version = "py311"
line-length = 110
exclude = ["rmbg_onnx_runner/web"]

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I"]
```

- [ ] **Step 3: Remove the incomplete import stubs from the Web tests**

Delete the `cgi` and `rmbg_onnx` `sys.modules` manipulation at the top of `test_web_app.py`; after installing `requirements/dev.txt`, imports must use the real modules. Retain only:

```python
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import web_app
```

- [ ] **Step 4: Extend ignore rules without deleting local artifacts**

Append:

```gitignore
.venv/
*.log
*.onnx
models/
outputs/
rmbg_onnx_runner_windows_update_*.zip
.coverage
htmlcov/
dist/
build/
```

Do not remove the existing ZIP files from disk; verify only that `git status --short` no longer lists them.

- [ ] **Step 5: Create and populate the development environment**

Run:

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements/dev.txt
```

Expected: installation succeeds and `./.venv/bin/python -c "import flask, numpy, PIL, onnxruntime"` exits 0. Task 1 deliberately uses Python 3.12 because the pre-migration server still imports `cgi`; Python 3.13 is added to the test matrix after Task 3 removes that import.

- [ ] **Step 6: Run the pre-migration baseline**

Run:

```bash
./.venv/bin/python -m pytest -q
```

Expected: all current tests pass under the populated environment. If a test still fails, classify it as existing code, environment, or test isolation before changing migration code.

- [ ] **Step 7: Commit the test baseline explicitly**

```bash
git add .gitignore pyproject.toml requirements rmbg_onnx_runner/tests/test_web_app.py
git commit -m "build: establish cross-platform Python test environment"
```

### Task 2: Extract processing and manifest behavior from the HTTP layer

**Files:**
- Create: `rmbg_onnx_runner/task_service.py`
- Create: `rmbg_onnx_runner/tests/test_task_service.py`
- Modify: `rmbg_onnx_runner/web_app.py:24-345`
- Modify: `rmbg_onnx_runner/tests/test_web_app.py`

- [ ] **Step 1: Write failing service tests using real Werkzeug uploads**

Create `test_task_service.py` with this concrete upload fixture and processing contract:

```python
import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from werkzeug.datastructures import FileStorage, MultiDict

import task_service


class FakeSession:
    def __init__(self):
        self.calls = []

    def remove_background(self, input_path, output_path, **options):
        self.calls.append((Path(input_path), Path(output_path), options))
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"result")
        return SimpleNamespace(inference_seconds=0.12)


def upload(name="first.png", data=b"image"):
    return FileStorage(stream=io.BytesIO(data), filename=name, content_type="image/png")


def test_options_from_form_preserves_existing_defaults():
    options = task_service.options_from_form(MultiDict())
    assert options == task_service.ProcessOptions()


def test_iter_process_events_streams_start_item_done_and_manifest():
    session = FakeSession()
    with tempfile.TemporaryDirectory() as tmpdir:
        events = list(
            task_service.iter_process_events(
                fields=[upload()],
                relative_paths=["folder/first.png"],
                output_root=Path(tmpdir),
                session=session,
                run_id="20260722-120000",
            )
        )
        manifest = json.loads(
            (Path(tmpdir) / "20260722-120000" / "manifest.json").read_text(encoding="utf-8")
        )

    assert [event["type"] for event in events] == ["start", "item", "done"]
    assert events[1]["item"]["outputName"] == "first_rmbg.png"
    assert manifest["status"] == "done"
    assert manifest["success"] == 1
```

Add these named tests in the same file so every existing contract has an explicit home:

```python
def test_line_art_uses_lineart_suffix_and_manifest_mode():
    session = FakeSession()
    with tempfile.TemporaryDirectory() as tmpdir:
        events = list(
            task_service.iter_process_events(
                fields=[upload("drawing.png")],
                relative_paths=["drawing.png"],
                output_root=Path(tmpdir),
                session=session,
                run_id="20260722-121000",
                options=task_service.ProcessOptions(processing_mode="line_art"),
            )
        )
        manifest = json.loads(
            (Path(tmpdir) / "20260722-121000" / "manifest.json").read_text(encoding="utf-8")
        )
    assert events[1]["item"]["outputName"] == "drawing_lineart.png"
    assert manifest["options"]["processingMode"] == "line_art"


def test_output_options_reach_session():
    session = FakeSession()
    options = task_service.ProcessOptions(
        processing_mode="line_art",
        output_format="webp",
        edge_optimize=True,
        transparent_background=False,
        background_color="#ffeecc",
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        list(
            task_service.iter_process_events(
                fields=[upload()],
                relative_paths=["first.png"],
                output_root=Path(tmpdir),
                session=session,
                run_id="20260722-122000",
                options=options,
            )
        )
    assert session.calls[0][2] == {
        "processing_mode": "line_art",
        "output_format": "webp",
        "edge_optimize": True,
        "transparent_background": False,
        "background_color": "#ffeecc",
    }


def test_recent_tasks_are_newest_first():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        for run_id in ["20260722-120000", "20260722-121500"]:
            run_dir = root / run_id
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text(
                json.dumps({"schemaVersion": 1, "runId": run_id}), encoding="utf-8"
            )
        tasks = task_service.load_recent_tasks(root, limit=2)
    assert [task["runId"] for task in tasks] == ["20260722-121500", "20260722-120000"]
```

- [ ] **Step 2: Run the new test and verify the missing module failure**

Run:

```bash
./.venv/bin/python -m pytest rmbg_onnx_runner/tests/test_task_service.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'task_service'`.

- [ ] **Step 3: Create the service boundary**

Move these definitions from `web_app.py` into `task_service.py` without changing their external JSON contract:

```python
IMAGE_EXTENSIONS
MANIFEST_NAME
ProcessOptions
safe_relative_path
output_name
is_supported_image
now_text
process_options_payload
write_task_manifest
load_task_manifest
load_recent_tasks
result_dir_for_run
parse_bool
process_item
iter_process_events
```

Replace CGI-specific parsing with this complete function:

```python
from werkzeug.datastructures import MultiDict


def options_from_form(form: MultiDict[str, str]) -> ProcessOptions:
    processing_mode = rmbg_onnx.normalize_processing_mode(form.get("processingMode", "rmbg"))
    output_format = rmbg_onnx.normalize_output_format(form.get("outputFormat", "png"))
    edge_optimize = parse_bool(form.get("edgeOptimize", "false"), default=False)
    transparent_background = parse_bool(form.get("transparentBackground", "true"), default=True)
    background_color = form.get("backgroundColor", "#FFFFFF") or "#FFFFFF"
    rmbg_onnx.normalize_background_color(background_color)
    return ProcessOptions(
        processing_mode=processing_mode,
        output_format=output_format,
        edge_optimize=edge_optimize,
        transparent_background=transparent_background,
        background_color=background_color,
    )
```

Change `process_item` to persist Werkzeug `FileStorage` safely:

```python
source_path = input_dir / relative_path
source_path.parent.mkdir(parents=True, exist_ok=True)
field.save(source_path)
field.stream.seek(0)
```

The moved implementation must preserve these exact values: schema version `1`; event order `start`, one `item` per upload, then `done`; task directories `_uploads/` and `results/`; suffixes `_rmbg` and `_lineart`; and per-item failure represented by `ok: false` plus `message` without terminating the remaining batch.

- [ ] **Step 4: Import the extracted definitions temporarily from the old server**

Replace the moved definitions in `web_app.py` with explicit imports:

```python
from task_service import (
    ProcessOptions,
    iter_process_events,
    load_recent_tasks,
    options_from_form,
    result_dir_for_run,
)
```

Update the old handler to call `options_from_form` only after adapting its CGI field values into a `MultiDict`. This temporary bridge is deleted in Task 3; it only keeps Task 2 independently testable.

- [ ] **Step 5: Run service and full tests**

```bash
./.venv/bin/python -m pytest rmbg_onnx_runner/tests/test_task_service.py -q
./.venv/bin/python -m pytest -q
```

Expected: both commands pass; manifests and output URLs remain byte-for-byte compatible with current tests.

- [ ] **Step 6: Commit the extraction**

```bash
git add rmbg_onnx_runner/task_service.py rmbg_onnx_runner/web_app.py rmbg_onnx_runner/tests
git commit -m "refactor: separate task processing from HTTP transport"
```

### Task 3: Replace the HTTP handler with a Flask application factory

**Files:**
- Replace: `rmbg_onnx_runner/web_app.py`
- Replace: `rmbg_onnx_runner/tests/test_web_app.py`

- [ ] **Step 1: Write Flask route contract tests**

Use a `FakeSession` and construct state without loading an ONNX model:

```python
import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import web_app


class FakeSession:
    provider_requested = ["CPUExecutionProvider"]
    provider_active = ["CPUExecutionProvider"]
    load_seconds = 0.01
    model_input = SimpleNamespace(shape=[1, 3, 1024, 1024], type="tensor(float)")

    def remove_background(self, input_path, output_path, **options):
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"result")
        return SimpleNamespace(inference_seconds=0.02)


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        state = web_app.WebAppState(
            model_path=Path(tmpdir) / "model.onnx",
            output_root=Path(tmpdir) / "outputs",
            provider="cpu",
            session=FakeSession(),
            access_token="test-token",
            server_origin="http://127.0.0.1:8765",
        )
        app = web_app.create_app(state, max_upload_mb=16)
        app.config.update(TESTING=True)
        with app.test_client() as test_client:
            response = test_client.get("/?token=test-token", headers={"Host": "127.0.0.1:8765"})
            assert response.status_code == 200
            yield test_client


def test_status_preserves_provider_contract(client):
    response = client.get("/api/status", headers={"Host": "127.0.0.1:8765"})
    assert response.status_code == 200
    assert response.get_json()["providerActive"] == ["CPUExecutionProvider"]


def test_process_streams_ndjson(client):
    response = client.post(
        "/api/process",
        data={
            "processingMode": "rmbg",
            "outputFormat": "png",
            "files": (io.BytesIO(b"image"), "first.png"),
            "paths": "folder/first.png",
        },
        headers={"Host": "127.0.0.1:8765", "Accept": "application/x-ndjson"},
    )
    events = [json.loads(line) for line in response.text.splitlines()]
    assert response.status_code == 200
    assert [event["type"] for event in events] == ["start", "item", "done"]
```

- [ ] **Step 2: Run the route tests and verify the factory is missing**

```bash
./.venv/bin/python -m pytest rmbg_onnx_runner/tests/test_web_app.py -q
```

Expected: FAIL because `create_app` and the extended `WebAppState` do not exist.

- [ ] **Step 3: Replace the handler with the Flask factory**

Implement these core definitions in `web_app.py`:

```python
from __future__ import annotations

import argparse
import json
import platform
from dataclasses import dataclass
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from werkzeug.exceptions import RequestEntityTooLarge

import rmbg_onnx
from task_service import iter_process_events, load_recent_tasks, options_from_form, result_dir_for_run


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

    @app.get("/<path:name>")
    def static_asset(name: str):
        return send_from_directory(WEB_DIR, name)

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
        if "application/x-ndjson" in request.accept_mimetypes:
            def lines():
                for event in events:
                    yield json.dumps(event, ensure_ascii=False) + "\n"
            return Response(stream_with_context(lines()), content_type="application/x-ndjson; charset=utf-8")
        final_event = next(event for event in events if event["type"] == "done")
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

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return jsonify(error=f"上传内容超过 {max_upload_mb} MB 限制。"), 413

    return app
```

Add open-output/open-result routes in Task 4 together with their security contract. Do not keep `BaseHTTPRequestHandler`, `ThreadingHTTPServer`, `cgi`, manual MIME serving, `json_bytes`, or response-writing helpers.

- [ ] **Step 4: Correct non-streaming generator consumption**

The non-streaming route must consume every event before returning the final event so processing actually runs:

```python
final_event = None
for event in events:
    if event["type"] == "done":
        final_event = event
if final_event is None:
    return jsonify(error="处理失败，未生成结果。"), 500
payload = dict(final_event)
payload.pop("type", None)
return jsonify(payload)
```

- [ ] **Step 5: Run Flask and full tests**

```bash
./.venv/bin/python -m pytest rmbg_onnx_runner/tests/test_web_app.py -q
./.venv/bin/python -m pytest -q
```

Expected: Flask tests pass; no source or test imports `cgi`.

- [ ] **Step 6: Verify the removed dependency explicitly**

```bash
rg -n "\bimport cgi\b|cgi\.FieldStorage|BaseHTTPRequestHandler|ThreadingHTTPServer" rmbg_onnx_runner
```

Expected: no matches.

- [ ] **Step 7: Commit the Flask migration**

```bash
git add rmbg_onnx_runner/web_app.py rmbg_onnx_runner/tests/test_web_app.py
git commit -m "feat: migrate local web service to Flask"
```

### Task 4: Add local-only authentication, safe side-effect routes, and startup lifecycle

**Files:**
- Create: `rmbg_onnx_runner/runtime.py`
- Create: `rmbg_onnx_runner/tests/test_runtime.py`
- Modify: `rmbg_onnx_runner/web_app.py`
- Modify: `rmbg_onnx_runner/tests/test_web_app.py`

- [ ] **Step 1: Write failing authentication and host tests**

Add:

```python
def test_root_rejects_wrong_token(client):
    response = client.get("/?token=wrong", headers={"Host": "127.0.0.1:8765"})
    assert response.status_code == 403


def test_api_rejects_missing_cookie(client):
    with client.application.test_client() as fresh_client:
        response = fresh_client.get(
            "/api/status", headers={"Host": "127.0.0.1:8765"}
        )
        assert response.status_code == 403


def test_rejects_untrusted_host(client):
    response = client.get("/api/status", headers={"Host": "evil.example"})
    assert response.status_code == 403


def test_open_output_is_post_only(client):
    assert client.get("/api/open-output", headers={"Host": "127.0.0.1:8765"}).status_code == 405
```

- [ ] **Step 2: Write failing runtime tests**

Create `test_runtime.py`:

```python
import socket

import pytest

import runtime


def test_require_loopback_rejects_remote_bind():
    with pytest.raises(ValueError, match="loopback"):
        runtime.require_loopback("0.0.0.0")


def test_find_available_port_skips_bound_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    occupied = sock.getsockname()[1]
    try:
        selected = runtime.find_available_port("127.0.0.1", occupied, attempts=2)
    finally:
        sock.close()
    assert selected != occupied
```

- [ ] **Step 3: Implement runtime helpers**

Create `runtime.py` with these interfaces:

```python
from __future__ import annotations

import os
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path


LOOPBACK_HOSTS = {"127.0.0.1", "localhost"}


def require_loopback(host: str) -> str:
    if host not in LOOPBACK_HOSTS:
        raise ValueError("host must be a loopback address: 127.0.0.1 or localhost")
    return host


def find_available_port(host: str, preferred: int, attempts: int = 20) -> int:
    require_loopback(host)
    for port in range(preferred, preferred + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"no available local port in {preferred}-{preferred + attempts - 1}")


def open_in_file_manager(path: Path) -> None:
    target = path.resolve()
    if sys.platform == "win32":
        args = ["explorer", f"/select,{target}"] if target.is_file() else ["explorer", str(target)]
    elif sys.platform == "darwin":
        args = ["open", "-R", str(target)] if target.is_file() else ["open", str(target)]
    else:
        folder = target.parent if target.is_file() else target
        args = ["xdg-open", str(folder)]
    subprocess.Popen(args)


def open_web_page(url: str) -> None:
    webbrowser.open(url)
```

- [ ] **Step 4: Add Flask request guards**

Inside `create_app`, add:

```python
import secrets
from flask import abort


def valid_host() -> bool:
    return request.host == "127.0.0.1" or request.host.startswith("127.0.0.1:") \
        or request.host == "localhost" or request.host.startswith("localhost:")


@app.before_request
def protect_local_service():
    if not valid_host():
        abort(403)
    supplied = request.args.get("token", "") if request.path == "/" else request.cookies.get("koutu_access", "")
    if not secrets.compare_digest(supplied, state.access_token):
        abort(403)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("Origin")
        if origin and origin != state.server_origin:
            abort(403)
```

Add response headers:

```python
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
```

- [ ] **Step 5: Implement POST-only folder routes**

```python
from runtime import open_in_file_manager


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
```

Patch `open_in_file_manager` in tests so no GUI application launches.

- [ ] **Step 6: Implement CLI and Waitress startup**

Add CLI parsing with defaults `--host 127.0.0.1`, `--port 8765`, `--provider auto`, `--max-upload-mb 1024`, `--open`, `--strict-provider`. The startup sequence must be:

```python
host = require_loopback(args.host)
port = find_available_port(host, args.port)
token = secrets.token_urlsafe(32)
origin = f"http://{host}:{port}"
state = load_state(args, access_token=token, server_origin=origin)
app = create_app(state, max_upload_mb=args.max_upload_mb)
url = f"{origin}/?token={token}"
print(f"Server ready: {origin}/")
print("The access token is embedded in the opened local URL.")
if args.open:
    threading.Timer(0.5, open_web_page, args=(url,)).start()
serve(app, host=host, port=port, threads=4)
```

Import `serve` from `waitress`, catch model/provider initialization failures before starting the server, and exit nonzero with the existing diagnostic text.

- [ ] **Step 7: Run focused and full tests**

```bash
./.venv/bin/python -m pytest rmbg_onnx_runner/tests/test_runtime.py rmbg_onnx_runner/tests/test_web_app.py -q
./.venv/bin/python -m pytest -q
```

Expected: all tests pass; unauthenticated and remote-host requests receive 403; GET side-effect routes receive 405.

- [ ] **Step 8: Commit local-service hardening**

```bash
git add rmbg_onnx_runner/runtime.py rmbg_onnx_runner/web_app.py rmbg_onnx_runner/tests
git commit -m "feat: harden localhost service and startup lifecycle"
```

### Task 5: Make ONNX provider selection portable

**Files:**
- Modify: `rmbg_onnx_runner/rmbg_onnx.py:47-101,176-264`
- Modify: `rmbg_onnx_runner/check_env.py`
- Modify: `rmbg_onnx_runner/run_rmbg_onnx.py`
- Modify: `rmbg_onnx_runner/tests/test_rmbg_onnx.py`

- [ ] **Step 1: Write the provider matrix tests**

```python
def test_auto_prefers_coreml_on_macos():
    providers = rmbg_onnx.choose_providers(
        "auto",
        available=["CoreMLExecutionProvider", "CPUExecutionProvider"],
        system="Darwin",
    )
    assert providers == ["CoreMLExecutionProvider", "CPUExecutionProvider"]


def test_auto_prefers_cuda_outside_macos():
    providers = rmbg_onnx.choose_providers(
        "auto",
        available=["CUDAExecutionProvider", "CPUExecutionProvider"],
        system="Windows",
    )
    assert providers == ["CUDAExecutionProvider", "CPUExecutionProvider"]


def test_auto_falls_back_to_cpu():
    assert rmbg_onnx.choose_providers(
        "auto", available=["CPUExecutionProvider"], system="Linux"
    ) == ["CPUExecutionProvider"]


def test_explicit_coreml_requires_provider():
    with pytest.raises(RuntimeError, match="CoreMLExecutionProvider"):
        rmbg_onnx.choose_providers("coreml", available=["CPUExecutionProvider"], system="Darwin")
```

Add `import pytest` to the test module because the new explicit-provider assertion uses `pytest.raises`.

- [ ] **Step 2: Run the tests and verify signature failure**

```bash
./.venv/bin/python -m pytest rmbg_onnx_runner/tests/test_rmbg_onnx.py -q
```

Expected: FAIL because `system` and `coreml` are unsupported.

- [ ] **Step 3: Implement portable provider ordering**

Replace `choose_providers` with:

```python
import platform


def choose_providers(
    provider: str,
    available: Iterable[str] | None = None,
    system: str | None = None,
) -> list[str]:
    if available is None:
        import onnxruntime as ort
        available = ort.get_available_providers()
    available_set = set(available)
    system_name = system or platform.system()

    if provider == "cpu":
        return ["CPUExecutionProvider"]
    if provider == "cuda":
        if "CUDAExecutionProvider" not in available_set:
            raise RuntimeError(f"CUDAExecutionProvider is not available: {sorted(available_set)}")
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if provider == "coreml":
        if "CoreMLExecutionProvider" not in available_set:
            raise RuntimeError(f"CoreMLExecutionProvider is not available: {sorted(available_set)}")
        return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    if provider == "auto":
        if system_name == "Darwin" and "CoreMLExecutionProvider" in available_set:
            return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        if "CUDAExecutionProvider" in available_set:
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]
        return ["CPUExecutionProvider"]
    raise ValueError("provider must be one of: auto, cuda, coreml, cpu")
```

- [ ] **Step 4: Avoid unconditional NVIDIA preload on non-CUDA installations**

After importing ONNX Runtime, inspect available providers first and preload NVIDIA libraries only when CUDA is available:

```python
available_providers = ort.get_available_providers()
self.dll_directory_handles = []
if "CUDAExecutionProvider" in available_providers:
    self.dll_directory_handles = add_nvidia_dll_directories()
    if hasattr(ort, "preload_dlls"):
        ort.preload_dlls(directory="")
```

- [ ] **Step 5: Update all CLI choices and diagnostics**

Use the same choices in `web_app.py`, `check_env.py`, and `run_rmbg_onnx.py`:

```python
choices=["auto", "cuda", "coreml", "cpu"]
default="auto"
```

In `check_env.py`, call `nvidia-smi` only when CUDA is available and print:

```python
print(f"platform: {platform.platform()}")
print(f"python: {sys.version.split()[0]}")
print(f"onnxruntime: {ort.__version__}")
print(f"available providers: {available}")
print(f"selected providers: {choose_providers(args.provider, available=available)}")
if "CUDAExecutionProvider" in available:
    print(f"nvidia-smi: {run_nvidia_smi()}")
```

- [ ] **Step 6: Run tests and CLI help smoke checks**

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python rmbg_onnx_runner/web_app.py --help
./.venv/bin/python rmbg_onnx_runner/check_env.py --help
./.venv/bin/python rmbg_onnx_runner/run_rmbg_onnx.py --help
```

Expected: tests pass; every help output lists `auto,cuda,coreml,cpu`.

- [ ] **Step 7: Commit provider portability**

```bash
git add rmbg_onnx_runner/rmbg_onnx.py rmbg_onnx_runner/check_env.py rmbg_onnx_runner/run_rmbg_onnx.py rmbg_onnx_runner/tests/test_rmbg_onnx.py
git commit -m "feat: add portable ONNX provider selection"
```

### Task 6: Update the browser for the protected Flask API

**Files:**
- Modify: `rmbg_onnx_runner/web/index.html:15-25`
- Modify: `rmbg_onnx_runner/web/app.js:528-560`
- Modify: `rmbg_onnx_runner/tests/test_web_assets.py`

- [ ] **Step 1: Write failing asset contract tests**

Add assertions:

```python
def test_frontend_uses_dynamic_provider_badge_and_post_side_effects():
    markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
    script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

    assert 'id="providerBadge"' in markup
    assert ">GPU/CUDA<" not in markup
    assert 'method: "POST"' in script
    assert 'headers: { "Content-Type": "application/json" }' in script
    assert 'JSON.stringify({ path: item.outputPath })' in script
    assert 'JSON.stringify({ runId: state.currentRunId })' in script
```

- [ ] **Step 2: Run the asset test and verify it fails**

```bash
./.venv/bin/python -m pytest rmbg_onnx_runner/tests/test_web_assets.py -q
```

Expected: FAIL on the fixed CUDA badge and GET URLs.

- [ ] **Step 3: Make the provider badge dynamic**

Change the fixed badge to:

```html
<span id="providerBadge" class="pill">推理后端检测中</span>
```

Add it to the element map and update `loadStatus`:

```javascript
providerBadge: document.querySelector("#providerBadge"),

const active = Array.isArray(data.providerActive) ? data.providerActive.join(" / ") : "CPU";
els.statusText.textContent = `模型已加载，${active}`;
els.providerBadge.textContent = active;
els.statusText.classList.add("ready");
```

- [ ] **Step 4: Change folder-opening requests to JSON POST**

```javascript
async function openResultFolder(item) {
  if (!item.ok || !item.outputPath) return;
  try {
    const response = await fetch("/api/open-result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: item.outputPath }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "无法打开结果文件夹");
  } catch (error) {
    els.quotaText.textContent = error.message;
  }
}

async function openCurrentRunFolder() {
  if (!state.currentRunId) return;
  try {
    const response = await fetch("/api/open-output", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ runId: state.currentRunId }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "无法打开本次结果文件夹");
  } catch (error) {
    els.quotaText.textContent = error.message;
  }
}
```

- [ ] **Step 5: Add explicit 403/413 messaging**

In the process error branch, map status codes before using the server message:

```javascript
if (!response.ok) {
  const data = await response.json().catch(() => ({}));
  if (response.status === 403) throw new Error("本地服务访问令牌已失效，请重新运行启动脚本。");
  if (response.status === 413) throw new Error(data.error || "上传内容超过服务限制。");
  throw new Error(data.error || "处理失败");
}
```

- [ ] **Step 6: Run asset and full tests**

```bash
./.venv/bin/python -m pytest rmbg_onnx_runner/tests/test_web_assets.py -q
./.venv/bin/python -m pytest -q
```

Expected: pass; the browser contains no GET call to either open-folder endpoint.

- [ ] **Step 7: Commit frontend compatibility**

```bash
git add rmbg_onnx_runner/web rmbg_onnx_runner/tests/test_web_assets.py
git commit -m "feat: connect browser UI to protected Flask API"
```

### Task 7: Add cross-platform install and start scripts

**Files:**
- Create: `scripts/install_windows.ps1`
- Create: `scripts/start_windows.ps1`
- Create: `scripts/install_macos.sh`
- Create: `scripts/start_macos.sh`
- Create: `scripts/install_linux.sh`
- Create: `scripts/start_linux.sh`
- Create: `rmbg_onnx_runner/tests/test_repository.py`
- Delete: `rmbg_onnx_runner/install_windows.ps1`
- Delete: `rmbg_onnx_runner/requirements-win-gpu.txt`

- [ ] **Step 1: Write script contract tests**

Create `test_repository.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_platform_scripts_exist_and_use_local_venv():
    expected = [
        "install_windows.ps1",
        "start_windows.ps1",
        "install_macos.sh",
        "start_macos.sh",
        "install_linux.sh",
        "start_linux.sh",
    ]
    for name in expected:
        text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert ".venv" in text
        assert "web_app.py" in text or name.startswith("install_")


def test_source_distribution_does_not_reference_legacy_cgi():
    for path in (ROOT / "rmbg_onnx_runner").rglob("*.py"):
        assert "import cgi" not in path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run and verify missing scripts**

```bash
./.venv/bin/python -m pytest rmbg_onnx_runner/tests/test_repository.py -q
```

Expected: FAIL because `scripts/` does not exist.

- [ ] **Step 3: Implement Windows installation**

`scripts/install_windows.ps1` must:

```powershell
[CmdletBinding()]
param(
    [ValidateSet("auto", "cuda", "cpu")]
    [string]$Runtime = "auto"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (Get-Command py -ErrorAction SilentlyContinue) {
    $PySelector = $null
    foreach ($Version in @("3.13", "3.12", "3.11")) {
        & py "-$Version" -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PySelector = "-$Version"
            break
        }
    }
    if (-not $PySelector) { throw "Python 3.11-3.13 is required." }
    if (-not (Test-Path ".venv\Scripts\python.exe")) { & py $PySelector -m venv .venv }
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)"
    if ($LASTEXITCODE -ne 0) { throw "Python 3.11-3.13 is required." }
    if (-not (Test-Path ".venv\Scripts\python.exe")) { & python -m venv .venv }
} else {
    throw "Python was not found. Install Python 3.11-3.13 from python.org."
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if ($Runtime -eq "auto") {
    $Runtime = if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { "cuda" } else { "cpu" }
}
$Requirements = if ($Runtime -eq "cuda") { "requirements\windows-cuda.txt" } else { "requirements\cpu.txt" }

& $Python -m pip install --upgrade pip
& $Python -m pip install -r $Requirements
& $Python rmbg_onnx_runner\check_env.py --provider auto --model model.onnx
Write-Host "Environment ready. Run scripts\start_windows.ps1"
```

- [ ] **Step 4: Implement Windows startup**

`scripts/start_windows.ps1`:

```powershell
[CmdletBinding()]
param(
    [string]$Model = "model.onnx",
    [string]$OutputDir = "outputs",
    [ValidateSet("auto", "cuda", "coreml", "cpu")]
    [string]$Provider = "auto"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Environment missing. Run scripts\install_windows.ps1 first." }
if (-not (Test-Path $Model)) { throw "Model not found: $Model" }
& $Python rmbg_onnx_runner\web_app.py --model $Model --output-dir $OutputDir --provider $Provider --open
exit $LASTEXITCODE
```

- [ ] **Step 5: Implement macOS installation and startup**

`scripts/install_macos.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
python3 -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)' \
  || { echo "Python 3.11-3.13 is required." >&2; exit 1; }
test -x .venv/bin/python || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements/macos.txt
.venv/bin/python rmbg_onnx_runner/check_env.py --provider auto --model model.onnx
echo "Environment ready. Run ./scripts/start_macos.sh"
```

`scripts/start_macos.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
test -x .venv/bin/python || { echo "Run ./scripts/install_macos.sh first." >&2; exit 1; }
test -f model.onnx || { echo "Model not found: $project_root/model.onnx" >&2; exit 1; }
exec .venv/bin/python rmbg_onnx_runner/web_app.py \
  --model model.onnx --output-dir outputs --provider auto --open "$@"
```

- [ ] **Step 6: Implement Linux installation and startup**

`scripts/install_linux.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
requirements="requirements/cpu.txt"
if [[ "${1:-}" == "--cuda" ]]; then
  requirements="requirements/linux-cuda.txt"
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--cuda]" >&2
  exit 2
fi
python3 -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)' \
  || { echo "Python 3.11-3.13 is required." >&2; exit 1; }
test -x .venv/bin/python || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r "$requirements"
.venv/bin/python rmbg_onnx_runner/check_env.py --provider auto --model model.onnx
echo "Environment ready. Run ./scripts/start_linux.sh"
```

`scripts/start_linux.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"
test -x .venv/bin/python || { echo "Run ./scripts/install_linux.sh first." >&2; exit 1; }
test -f model.onnx || { echo "Model not found: $project_root/model.onnx" >&2; exit 1; }
exec .venv/bin/python rmbg_onnx_runner/web_app.py \
  --model model.onnx --output-dir outputs --provider auto --open "$@"
```

- [ ] **Step 7: Make POSIX scripts executable and remove superseded files**

```bash
chmod +x scripts/install_macos.sh scripts/start_macos.sh scripts/install_linux.sh scripts/start_linux.sh
```

Delete only `rmbg_onnx_runner/install_windows.ps1` and `rmbg_onnx_runner/requirements-win-gpu.txt`; the new root scripts and requirements replace them.

- [ ] **Step 8: Validate scripts without starting the model**

```bash
bash -n scripts/install_macos.sh scripts/start_macos.sh scripts/install_linux.sh scripts/start_linux.sh
./.venv/bin/python -m pytest rmbg_onnx_runner/tests/test_repository.py -q
```

On Windows CI, parse the PowerShell AST:

```powershell
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile("scripts/install_windows.ps1", [ref]$tokens, [ref]$errors) | Out-Null
[System.Management.Automation.Language.Parser]::ParseFile("scripts/start_windows.ps1", [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count -gt 0) { $errors | Format-List; exit 1 }
```

- [ ] **Step 9: Commit platform scripts**

```bash
git add scripts requirements rmbg_onnx_runner/tests/test_repository.py
git add -u rmbg_onnx_runner/install_windows.ps1 rmbg_onnx_runner/requirements-win-gpu.txt
git commit -m "feat: add cross-platform source install and start scripts"
```

### Task 8: Write public documentation, licensing, and repository hygiene

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `SECURITY.md`
- Modify: `rmbg_onnx_runner/README.md`
- Modify: `rmbg_onnx_runner/tests/test_repository.py`

- [ ] **Step 1: Add failing documentation contract tests**

```python
def test_public_docs_cover_install_security_and_model_license():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

    for text in ["Windows", "macOS", "Linux", "127.0.0.1", "model.onnx"]:
        assert text in readme
    assert "CC BY-NC 4.0" in notices
    assert "commercial" in notices.lower()
    assert "localhost" in security.lower()
```

- [ ] **Step 2: Run and verify missing public files**

```bash
./.venv/bin/python -m pytest rmbg_onnx_runner/tests/test_repository.py -q
```

Expected: FAIL because the public files do not exist.

- [ ] **Step 3: Write the root README in answer-first order**

Use these sections and commands:

```markdown
# 一键抠图 Local Web Runner

图片只在本机处理。程序启动 Flask 服务并在浏览器打开 `127.0.0.1`，不提供公网服务。

## 功能
## 支持平台
## 模型授权说明
## Windows 安装与启动
## macOS 安装与启动
## Linux 安装与启动
## CPU/GPU 后端
## 输出目录与任务恢复
## 安全边界
## 常见问题
## 开发与测试
## 发布流程
```

Document exact commands:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start_windows.ps1
```

```bash
./scripts/install_macos.sh
./scripts/start_macos.sh
```

```bash
./scripts/install_linux.sh        # CPU
./scripts/install_linux.sh --cuda # NVIDIA CUDA
./scripts/start_linux.sh
```

State that the user must place an authorized `model.onnx` at repository root, that line-art mode does not use the model, and that `--host 0.0.0.0` is deliberately unsupported.

- [ ] **Step 4: Add exact licensing boundaries**

Create `LICENSE` with the complete MIT text:

```text
MIT License

Copyright (c) 2026 RMBG ONNX Runner contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

In `THIRD_PARTY_NOTICES.md`, state:

```markdown
## BRIA RMBG-2.0

- Upstream: https://huggingface.co/briaai/RMBG-2.0
- Model license: Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)
- The model weights are not included in this repository or its GitHub Releases.
- Commercial use of the model requires a separate agreement with BRIA AI.

The MIT license in this repository applies to the application source and does not replace or broaden the model license.
```

- [ ] **Step 5: Add the security policy**

`SECURITY.md` must say:

```markdown
# Security Policy

This project supports local loopback use only. Do not expose the Flask service through `0.0.0.0`, port forwarding, reverse proxies, or public tunnels.

Report suspected path traversal, unauthorized local API access, malicious image handling, dependency compromise, or model-download integrity issues through a private GitHub Security Advisory. Do not include private images, model files, tokens, or machine paths in a public issue.
```

- [ ] **Step 6: Convert the inner README to developer details**

Keep the existing algorithm and output-layout explanation, but lead with a link to `../README.md`, replace Windows-only setup commands with the root scripts, and document the internal modules `task_service.py`, `runtime.py`, `web_app.py`, and `rmbg_onnx.py`.

- [ ] **Step 7: Run documentation and hygiene checks**

```bash
./.venv/bin/python -m pytest rmbg_onnx_runner/tests/test_repository.py -q
git status --short
git check-ignore model.onnx outputs/example.png rmbg_onnx_runner_windows_update_20260722-151258.zip
```

Expected: tests pass; all three sample artifacts are ignored; no ZIP is staged.

- [ ] **Step 8: Commit public repository documentation**

```bash
git add README.md LICENSE THIRD_PARTY_NOTICES.md SECURITY.md rmbg_onnx_runner/README.md rmbg_onnx_runner/tests/test_repository.py .gitignore
git commit -m "docs: prepare repository for public source release"
```

### Task 9: Add three-platform continuous integration

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the CI workflow**

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ["3.11", "3.12", "3.13"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      - name: Install test dependencies
        run: python -m pip install -r requirements/dev.txt
      - name: Run tests
        run: python -m pytest -q
      - name: Lint Python
    run: python -m ruff check rmbg_onnx_runner
      - name: Verify CLI imports without a model
        run: python rmbg_onnx_runner/web_app.py --help

  script-syntax:
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - name: Check POSIX scripts
        if: runner.os == 'Linux'
        run: bash -n scripts/*.sh
      - name: Check PowerShell scripts
        if: runner.os == 'Windows'
        shell: pwsh
        run: |
          $tokens = $null
          $errors = $null
          Get-ChildItem scripts/*.ps1 | ForEach-Object {
            [System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$errors) | Out-Null
          }
          if ($errors.Count -gt 0) { $errors | Format-List; exit 1 }
```

- [ ] **Step 2: Validate YAML and local checks**

Apply deterministic import/order fixes once, review them, then run the same checks the current platform can execute:

```bash
./.venv/bin/python -m ruff check --fix rmbg_onnx_runner
git diff -- rmbg_onnx_runner
./.venv/bin/python -m pytest -q
./.venv/bin/python -m ruff check rmbg_onnx_runner
bash -n scripts/*.sh
```

Expected: all pass. Inspect `.github/workflows/ci.yml` to confirm no secret is required and the model is not downloaded.

- [ ] **Step 3: Commit CI**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: test source runner on Windows macOS and Linux"
```

### Task 10: Add tag-driven GitHub source releases

**Files:**
- Create: `.github/workflows/release-source.yml`
- Modify: `README.md`

- [ ] **Step 1: Create the release workflow**

```yaml
name: release-source

on:
  push:
    tags:
      - "v*"

permissions:
  contents: write

jobs:
  verify-and-release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
      - name: Install test dependencies
        run: python -m pip install -r requirements/dev.txt
      - name: Test
        run: python -m pytest -q
      - name: Lint
        run: python -m ruff check rmbg_onnx_runner
      - name: Create GitHub source release
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh release create "$GITHUB_REF_NAME" --verify-tag --generate-notes --title "$GITHUB_REF_NAME"
```

GitHub automatically attaches source ZIP and tar archives to the release. Do not create or upload custom bundles containing ignored model/runtime files.

- [ ] **Step 2: Document the maintainer release command**

Add to README:

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

State that the tag workflow runs tests first and that a failed workflow must not be replaced by a manual unverified release.

- [ ] **Step 3: Inspect workflow permissions and artifact scope**

```bash
rg -n "contents: write|gh release create|model\.onnx|onnxruntime-gpu|dist/" .github README.md
```

Expected: write permission exists only in `release-source.yml`; no workflow packages or uploads a model.

- [ ] **Step 4: Commit source release automation**

```bash
git add .github/workflows/release-source.yml README.md
git commit -m "ci: publish verified GitHub source releases"
```

### Task 11: Run final automated, manual, and release-readiness verification

**Files:**
- Modify only if a verification finding requires a scoped fix.

- [ ] **Step 1: Review the complete diff and repository contents**

```bash
git status --short
git diff --check
git log --oneline --decorate -12
git ls-files | sort
```

Expected: no whitespace errors; no model, outputs, `.venv`, secrets, or historical ZIP files tracked.

- [ ] **Step 2: Run the full local automated suite**

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m ruff check rmbg_onnx_runner
bash -n scripts/*.sh
./.venv/bin/python rmbg_onnx_runner/web_app.py --help
./.venv/bin/python rmbg_onnx_runner/check_env.py --provider auto --model model.onnx
```

Expected: tests/lint/syntax/help pass. `check_env.py` may report that the ignored model is absent, but must exit successfully after reporting available providers.

- [ ] **Step 3: Perform a real CPU browser smoke test**

With an authorized `model.onnx` at repository root:

```bash
./scripts/start_macos.sh --provider cpu
```

On the active platform use its corresponding script. Verify in the browser:

1. The startup URL contains a token and the page loads.
2. Opening the bare server URL in a private window without the token returns 403.
3. Single image and nested-folder batch uploads complete.
4. NDJSON progress updates one item at a time.
5. PNG, WebP, transparent background, colored background, edge optimization, and line-art mode each produce expected files.
6. Refresh restores the latest manifest.
7. “打开本次结果文件夹” and result “定位” open only paths under the configured output root.
8. A request exceeding `--max-upload-mb` returns a Chinese 413 error.
9. Ctrl+C stops Waitress and releases the ONNX session.

- [ ] **Step 4: Perform platform/provider smoke tests**

- Windows NVIDIA: run `scripts\install_windows.ps1 -Runtime cuda`, confirm `CUDAExecutionProvider` appears in `/api/status`, and compare one result with CPU.
- Apple Silicon: run `scripts/install_macos.sh`, confirm whether `CoreMLExecutionProvider` is active; if unavailable, confirm clean CPU fallback and record the exact ONNX Runtime provider list.
- Linux/CPU: install with `scripts/install_linux.sh`, confirm CPU startup without NVIDIA tools.

Do not claim CoreML or CUDA support from package installation alone; the visible `/api/status` provider and a completed inference are required evidence.

- [ ] **Step 5: Verify clean-checkout installation**

Use a disposable clone or Git worktree, not the current dirty directory. Run the documented install command, place the authorized model manually, run the documented start command, and confirm no undocumented environment variable or file is required.

- [ ] **Step 6: Push and inspect GitHub Actions before tagging**

Push the branch, confirm every matrix job is green, inspect logs for dependency/provider fallbacks, and only then create `v0.1.0`.

- [ ] **Step 7: Verify the published release**

Download GitHub’s generated source ZIP on a clean machine. Confirm it contains the six scripts, requirements, Flask source, docs, and tests; confirm it contains no `model.onnx`, `.venv`, output images, credentials, or historical update ZIP.

- [ ] **Step 8: Record verification evidence**

In the release notes, list the exact tested OS/Python/provider combinations and clearly separate:

```text
CI confirmed: imports, unit tests, Flask routes, script syntax.
Runtime confirmed: named OS/GPU/provider combinations that completed real inference.
Not verified: untested GPU vendors, older OS versions, and public-network deployment (unsupported).
```

## 5. Rollback boundaries

- Tasks 1-2 do not change the public server implementation and can be reverted independently.
- Task 3 is the transport cutover. If Flask integration fails, revert Task 3 while retaining Task 2’s processing extraction.
- Task 4 is security/lifecycle hardening. Do not weaken it to restore compatibility; fix the browser cookie/origin behavior instead.
- Task 5 provider changes must always preserve explicit `--provider cpu` as the emergency path.
- Platform scripts and GitHub workflows do not modify model/output data and can be reverted independently.
- Never restore `cgi` as a compatibility fix; supported Python includes versions where it no longer exists.

## 6. Self-review results

- **Spec coverage:** Flask migration, browser preservation, cross-platform dependencies/scripts, local security, provider portability, GitHub source publishing, licensing, CI, and verification each have an explicit task.
- **Placeholder scan:** No implementation step depends on an unspecified function, route, command, or file. Windows, macOS, and Linux script bodies are all written out with their version checks, dependency selection, model checks, and startup commands.
- **Type consistency:** `WebAppState`, `ProcessOptions`, `options_from_form`, `iter_process_events`, `create_app`, runtime helper names, API paths, form fields, and JSON properties are consistent across implementation and tests.
- **Risk boundary:** Model acquisition and commercial authorization remain external release gates; this plan does not silently redistribute weights.
