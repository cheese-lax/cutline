# Model Runtime Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start the local web service independently from model availability, manage ONNX models in a dedicated inference process, restore the last successful model, expose selectable execution providers, and return evidence-based failure diagnostics including memory snapshots.

**Architecture:** Waitress/Flask remains a loopback-only control plane and never owns an `onnxruntime.InferenceSession`. A `ModelManager` in the Flask process starts one spawn-based inference worker, rejects switching while a batch is active, confirms the old worker has exited before starting the replacement, and exposes a lease-backed session proxy to the existing task pipeline. Runtime preferences and structured diagnostics stay in the Flask process; model loading and inference stay in the worker.

**Tech Stack:** Python 3.11-3.13, Flask 3.x, Waitress 3.x, `multiprocessing` with the `spawn` context, ONNX Runtime 1.26, psutil, vanilla JavaScript, pytest, Ruff

---

## Scope and fixed decisions

- The service starts and serves the UI when `models/` is empty.
- Model startup precedence is explicit `--model`, then the last successfully loaded model, then the first case-insensitively sorted model ID.
- The last model is persisted by the backend only after a worker reports `ready`; browser `localStorage` no longer triggers a second startup load.
- Provider selection supports `auto`, `cpu`, `cuda`, and `coreml`. Only providers available in the installed ONNX Runtime build are offered, while `auto` is always offered.
- CoreML is labelled `Apple CoreML`, not `GPU`, because CoreML can use CPU, GPU, or ANE and can fall back to CPU.
- A switch is rejected with HTTP 409 while any batch holds a runtime lease. No in-flight batch is forcefully terminated.
- Once switching starts, the old worker must be confirmed dead before the replacement starts. If replacement loading fails, the manager attempts to restart the old selection without ever running both workers together.
- `disable_mem_pattern` remains `False` by default. Add a web-server CLI flag for controlled measurement, but do not claim that disabling memory patterns reduces model-weight memory.
- Failure diagnosis reports confirmed facts separately from likely causes. A text match such as `CUDA out of memory` is `likely`; a Python `MemoryError` is `confirmed`.
- Keep Host, Origin, access-token, response-header, and output-path security boundaries unchanged.
- The worktree was dirty when this plan was written. Before every commit, inspect `git diff` and stage only task-owned hunks; never reset or overwrite pre-existing changes.

## File map

**Create**

- `rmbg_onnx_runner/resource_diagnostics.py`: system/GPU memory snapshots and runtime error classification.
- `rmbg_onnx_runner/runtime_preferences.py`: atomic persistence of the last successful model ID.
- `rmbg_onnx_runner/model_worker.py`: child-process entry point and request/response protocol.
- `rmbg_onnx_runner/model_manager.py`: worker lifecycle, leases, state machine, switching, rollback, and proxy calls.
- `rmbg_onnx_runner/tests/test_resource_diagnostics.py`: deterministic memory/error classification tests.
- `rmbg_onnx_runner/tests/test_runtime_preferences.py`: persistence and corrupt-state tests.
- `rmbg_onnx_runner/tests/test_model_worker.py`: worker protocol tests with a fake session factory.
- `rmbg_onnx_runner/tests/test_model_manager.py`: no-overlap, busy, rollback, timeout, and proxy tests.

**Modify**

- `requirements/base.txt`: add psutil for cross-platform available-memory and RSS measurements.
- `rmbg_onnx_runner/web_app.py`: nullable startup state, manager-backed APIs, background initial load, and lease integration.
- `rmbg_onnx_runner/task_service.py`: accept a session protocol and preserve structured worker failures.
- `rmbg_onnx_runner/web/index.html`: provider selector, runtime status, and no-model download guidance.
- `rmbg_onnx_runner/web/app.js`: runtime polling, unified model/provider switching, success feedback, and diagnostic rendering.
- `rmbg_onnx_runner/web/style.css`: runtime states, help panel, toast, and resource diagnostics.
- `rmbg_onnx_runner/tests/test_web_app.py`: no-model startup, runtime APIs, leases, busy switching, and diagnostics.
- `rmbg_onnx_runner/tests/test_task_service.py`: OOM and worker-error payload preservation.
- `rmbg_onnx_runner/tests/test_web_assets.py`: selectors, messages, links, and diagnostic fields.
- `rmbg_onnx_runner/tests/test_repository.py`: dependency/docs/start-script assertions.
- `README.md`: lifecycle, model download, Provider labels, failure diagnosis, and memory-pattern guidance.
- `rmbg_onnx_runner/README.md`: module responsibilities and troubleshooting.

## Runtime state and API contract

`GET /api/status` returns HTTP 200 in every runtime state:

```json
{
  "ready": false,
  "runtimeState": "no_model",
  "model": null,
  "provider": "auto",
  "providerRequested": [],
  "providerActive": [],
  "loadSeconds": null,
  "inputShape": null,
  "inputType": null,
  "lastError": null
}
```

`GET /api/providers` returns UI-safe choices and the current selection:

```json
{
  "selected": "auto",
  "providers": [
    {"id": "auto", "label": "自动检测"},
    {"id": "coreml", "label": "Apple CoreML"},
    {"id": "cpu", "label": "CPU"}
  ]
}
```

`POST /api/runtime/select` accepts both settings so one switch creates only one worker:

```json
{"model": "model_fp16.onnx", "provider": "coreml"}
```

Success is returned only after the worker has loaded the model and sent metadata:

```json
{
  "ok": true,
  "active": "model_fp16.onnx",
  "provider": "coreml",
  "providerActive": ["CoreMLExecutionProvider", "CPUExecutionProvider"],
  "loadSeconds": 2.418
}
```

Busy switching returns HTTP 409. A load failure returns HTTP 400 with `error`, `detail`, `suggestion`, `confidence`, and `resources`; if rollback succeeds, it also returns `restoredModel`.

### Task 1: Add cross-platform resource diagnostics

**Files:**
- Modify: `requirements/base.txt`
- Create: `rmbg_onnx_runner/resource_diagnostics.py`
- Create: `rmbg_onnx_runner/tests/test_resource_diagnostics.py`

- [ ] **Step 1: Write failing tests for system memory, CUDA memory, and confidence**

```python
def test_memory_error_is_confirmed_oom(monkeypatch):
    monkeypatch.setattr(resource_diagnostics, "capture_resource_snapshot", fake_snapshot)
    failure = resource_diagnostics.diagnose_runtime_error(
        MemoryError("allocation failed"),
        stage="inference",
        provider_active=["CPUExecutionProvider"],
    )
    assert failure.code == "SYSTEM_OUT_OF_MEMORY"
    assert failure.confidence == "confirmed"
    assert failure.resources.available_system_memory_bytes == 768 * 1024**2
    assert "768 MiB" in failure.suggestion


def test_cuda_oom_text_is_likely_gpu_oom(monkeypatch):
    monkeypatch.setattr(resource_diagnostics, "capture_resource_snapshot", fake_cuda_snapshot)
    failure = resource_diagnostics.diagnose_runtime_error(
        RuntimeError("CUDA_ERROR_OUT_OF_MEMORY"),
        stage="inference",
        provider_active=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    assert failure.code == "GPU_OUT_OF_MEMORY"
    assert failure.confidence == "likely"
    assert failure.resources.cuda_free_memory_bytes == 512 * 1024**2
    assert "切换到 CPU" in failure.suggestion


def test_unknown_error_does_not_claim_oom(monkeypatch):
    monkeypatch.setattr(resource_diagnostics, "capture_resource_snapshot", fake_snapshot)
    failure = resource_diagnostics.diagnose_runtime_error(
        RuntimeError("provider execution failed"),
        stage="inference",
        provider_active=["CPUExecutionProvider"],
    )
    assert failure.code == "INFERENCE_FAILED"
    assert failure.confidence == "unknown"
```

- [ ] **Step 2: Run the focused tests and verify they fail because the module is absent**

Run: `.venv/bin/pytest rmbg_onnx_runner/tests/test_resource_diagnostics.py -q`

Expected: FAIL during collection with `ModuleNotFoundError: No module named 'resource_diagnostics'`.

- [ ] **Step 3: Add psutil to the shared dependency set**

Append to `requirements/base.txt`:

```text
psutil>=6,<8
```

Install only into the existing development environment:

```bash
.venv/bin/python -m pip install "psutil>=6,<8"
```

- [ ] **Step 4: Implement resource snapshots and error classification**

Create immutable `ResourceSnapshot` and `RuntimeFailure` dataclasses. Use `psutil.virtual_memory()` for total/available system memory, `psutil.Process().memory_info().rss` for server/worker RSS, and `nvidia-smi --query-gpu=memory.free,memory.total --format=csv,noheader,nounits` only when CUDA is active and the command exists.

Classification order must be exact:

```python
if isinstance(exc, MemoryError):
    code, confidence = "SYSTEM_OUT_OF_MEMORY", "confirmed"
elif cuda_active and any(token in message for token in CUDA_OOM_TOKENS):
    code, confidence = "GPU_OUT_OF_MEMORY", "likely"
elif any(token in message for token in SYSTEM_OOM_TOKENS):
    code, confidence = "SYSTEM_OUT_OF_MEMORY", "likely"
elif stage == "model_load":
    code, confidence = "MODEL_LOAD_FAILED", "unknown"
else:
    code, confidence = "INFERENCE_FAILED", "unknown"
```

The JSON payload must use byte counts, not preformatted strings:

```python
def to_payload(self) -> dict[str, object]:
    return {
        "code": self.code,
        "stage": self.stage,
        "reason": self.reason,
        "detail": self.detail,
        "suggestion": self.suggestion,
        "confidence": self.confidence,
        "resources": self.resources.to_payload(),
    }
```

Do not include tracebacks in API payloads. Keep exception type plus at most 500 normalized characters in `detail`.

- [ ] **Step 5: Run diagnostics tests and lint**

Run:

```bash
.venv/bin/pytest rmbg_onnx_runner/tests/test_resource_diagnostics.py -q
.venv/bin/ruff check rmbg_onnx_runner/resource_diagnostics.py rmbg_onnx_runner/tests/test_resource_diagnostics.py
```

Expected: all tests PASS and Ruff exits 0.

- [ ] **Step 6: Review and commit only task-owned changes**

```bash
git diff -- requirements/base.txt rmbg_onnx_runner/resource_diagnostics.py rmbg_onnx_runner/tests/test_resource_diagnostics.py
git add requirements/base.txt rmbg_onnx_runner/resource_diagnostics.py rmbg_onnx_runner/tests/test_resource_diagnostics.py
git commit -m "feat: add runtime resource diagnostics"
```

### Task 2: Persist and resolve the last successful model

**Files:**
- Create: `rmbg_onnx_runner/runtime_preferences.py`
- Create: `rmbg_onnx_runner/tests/test_runtime_preferences.py`
- Modify: `rmbg_onnx_runner/web_app.py`

- [ ] **Step 1: Write failing preference and precedence tests**

```python
def test_preferences_round_trip_atomically(tmp_path):
    path = tmp_path / ".runtime-state.json"
    save_last_model(path, "portraits/model_fp16.onnx")
    assert load_last_model(path) == "portraits/model_fp16.onnx"
    assert not path.with_suffix(".tmp").exists()


def test_corrupt_preferences_are_ignored(tmp_path):
    path = tmp_path / ".runtime-state.json"
    path.write_text("not json", encoding="utf-8")
    assert load_last_model(path) == ""


def test_explicit_model_wins_over_saved_model(tmp_path):
    selected = choose_startup_model(
        models_dir=tmp_path / "models",
        requested="explicit.onnx",
        saved="saved.onnx",
    )
    assert selected.name == "explicit.onnx"
```

- [ ] **Step 2: Run the tests and verify the missing functions fail**

Run: `.venv/bin/pytest rmbg_onnx_runner/tests/test_runtime_preferences.py -q`

Expected: FAIL because `runtime_preferences` and `choose_startup_model` do not exist.

- [ ] **Step 3: Implement atomic persistence without storing absolute paths**

Persist only this schema under `outputs/.runtime-state.json`:

```json
{"schemaVersion": 1, "lastModel": "model_fp16.onnx"}
```

Implementation contract:

```python
def save_last_model(path: Path, model_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps({"schemaVersion": 1, "lastModel": model_id}, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)
```

`load_last_model` returns an empty string for missing files, invalid JSON, unknown schema versions, non-string values, absolute paths, and `..` path segments.

- [ ] **Step 4: Extract startup selection from model loading**

Add `choose_startup_model(models_dir, requested, saved) -> Path | None` to `web_app.py`. It must reuse `resolve_model` for every non-empty candidate and fall back in this order:

```python
if requested:
    return resolve_requested_model(models_dir, requested)
if saved:
    try:
        return resolve_model(models_dir, saved)
    except ValueError:
        print(f"Saved model is unavailable, falling back: {saved}")
models = discover_models(models_dir)
return resolve_model(models_dir, str(models[0]["id"])) if models else None
```

Do not create an ONNX Session in this function.

- [ ] **Step 5: Run focused tests**

Run:

```bash
.venv/bin/pytest rmbg_onnx_runner/tests/test_runtime_preferences.py rmbg_onnx_runner/tests/test_web_app.py -q
```

Expected: all targeted tests PASS. Keep `choose_startup_model` additive in this task so the existing `WebAppState` contract remains intact until Task 5.

- [ ] **Step 6: Review and commit task-owned hunks**

```bash
git diff -- rmbg_onnx_runner/runtime_preferences.py rmbg_onnx_runner/tests/test_runtime_preferences.py rmbg_onnx_runner/web_app.py
git add rmbg_onnx_runner/runtime_preferences.py rmbg_onnx_runner/tests/test_runtime_preferences.py
git add -p rmbg_onnx_runner/web_app.py
git commit -m "feat: persist the last successful model"
```

### Task 3: Create the spawn-safe inference worker protocol

**Files:**
- Create: `rmbg_onnx_runner/model_worker.py`
- Create: `rmbg_onnx_runner/tests/test_model_worker.py`

- [ ] **Step 1: Write failing worker protocol tests using an in-process fake connection**

Test these exact messages:

```python
ready = {
    "type": "ready",
    "metadata": {
        "providerRequested": ["CPUExecutionProvider"],
        "providerActive": ["CPUExecutionProvider"],
        "loadSeconds": 0.01,
        "inputShape": [1, 3, 1024, 1024],
        "inputType": "tensor(float)",
    },
}

request = {
    "type": "remove_background",
    "requestId": "request-1",
    "kwargs": {
        "input_path": "/tmp/input.png",
        "output_path": "/tmp/output.png",
        "output_format": "png",
        "processing_mode": "rmbg",
    },
}
```

Assert that a successful inference response preserves `requestId` and returns the picklable `RmbgRunResult`. Assert that a failing inference sends an `inference_error` response with the same `requestId` and the complete `RuntimeFailure` payload. Assert that a failing load sends one structured `load_error` payload from `diagnose_runtime_error`. Assert that `shutdown` sends `{"type": "stopped"}` and exits the loop.

- [ ] **Step 2: Run and verify failure**

Run: `.venv/bin/pytest rmbg_onnx_runner/tests/test_model_worker.py -q`

Expected: FAIL because `model_worker` is absent.

- [ ] **Step 3: Implement a top-level spawn target**

The function must be importable by a spawned child and receive primitive/picklable arguments:

```python
def worker_main(
    connection,
    model_path: str,
    provider: str,
    disable_fallback: bool,
    disable_mem_pattern: bool,
) -> None:
    session = None
    try:
        session = rmbg_onnx.RmbgSession(
            model_path=model_path,
            provider=provider,
            disable_fallback=disable_fallback,
            disable_mem_pattern=disable_mem_pattern,
        )
        connection.send(ready_payload(session))
        serve_requests(connection, session)
    except BaseException as exc:
        connection.send(load_or_worker_error(exc, session))
    finally:
        session = None
        gc.collect()
        connection.close()
```

`serve_requests` accepts only `remove_background` and `shutdown`. It catches inference exceptions around each `remove_background` call and returns `{"type": "inference_error", "requestId": request_id, "error": failure.to_payload()}` without terminating the worker. Unknown commands return `PROTOCOL_ERROR`. Never evaluate arbitrary function names or accept arbitrary module paths.

- [ ] **Step 4: Verify the worker module has no Flask imports and passes tests**

Run:

```bash
.venv/bin/pytest rmbg_onnx_runner/tests/test_model_worker.py -q
.venv/bin/ruff check rmbg_onnx_runner/model_worker.py rmbg_onnx_runner/tests/test_model_worker.py
```

Expected: PASS and `rg -n "flask|waitress" rmbg_onnx_runner/model_worker.py` returns no matches.

- [ ] **Step 5: Commit**

```bash
git add rmbg_onnx_runner/model_worker.py rmbg_onnx_runner/tests/test_model_worker.py
git commit -m "feat: add isolated inference worker"
```

### Task 4: Implement ModelManager lifecycle, leases, and no-overlap switching

**Files:**
- Create: `rmbg_onnx_runner/model_manager.py`
- Create: `rmbg_onnx_runner/tests/test_model_manager.py`

- [ ] **Step 1: Write lifecycle tests before implementation**

Use injected fake process and pipe factories; do not start ONNX Runtime in unit tests. Cover:

```python
def test_switch_stops_old_worker_before_starting_new(fake_runtime):
    manager = fake_runtime.manager()
    manager.start(selection("first.onnx"))
    manager.switch(selection("second.onnx"))
    assert fake_runtime.events == [
        "start:first.onnx",
        "ready:first.onnx",
        "shutdown:first.onnx",
        "join:first.onnx",
        "start:second.onnx",
        "ready:second.onnx",
    ]


def test_switch_is_rejected_while_batch_lease_is_active(fake_runtime):
    manager = fake_runtime.ready_manager()
    lease = manager.acquire()
    with pytest.raises(RuntimeBusyError):
        manager.switch(selection("second.onnx"))
    lease.close()


def test_failed_replacement_restarts_old_selection_without_overlap(fake_runtime):
    manager = fake_runtime.ready_manager("first.onnx")
    fake_runtime.fail_load("broken.onnx")
    with pytest.raises(RuntimeLoadError) as captured:
        manager.switch(selection("broken.onnx"))
    assert captured.value.restored_model == "first.onnx"
    assert fake_runtime.maximum_live_processes == 1
```

Also test graceful shutdown timeout followed by `terminate`, then `kill`, and assert that a new process is never started while `old_process.is_alive()` remains true.

- [ ] **Step 2: Run and verify failure**

Run: `.venv/bin/pytest rmbg_onnx_runner/tests/test_model_manager.py -q`

Expected: FAIL because `model_manager` is absent.

- [ ] **Step 3: Implement the state machine and metadata**

Use these states only:

```python
RUNTIME_STATES = {"no_model", "loading", "ready", "processing", "switching", "error", "stopped"}
```

Use immutable configuration and metadata:

```python
@dataclass(frozen=True)
class RuntimeSelection:
    model_id: str
    model_path: Path
    provider: str
    disable_fallback: bool = False
    disable_mem_pattern: bool = False


@dataclass(frozen=True)
class RuntimeMetadata:
    provider_requested: list[object]
    provider_active: list[str]
    load_seconds: float
    input_shape: list[object]
    input_type: str
```

The manager owns one `multiprocessing.get_context("spawn")`, one process, one parent connection, one `threading.RLock`, one RPC lock, and an active lease count.

- [ ] **Step 4: Implement strict stop-before-start behavior**

Use bounded escalation:

```python
def _stop_worker(self) -> None:
    process = self._process
    if process is None:
        return
    self._request_shutdown_if_responsive()
    process.join(self._shutdown_timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(self._shutdown_timeout_seconds)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(self._shutdown_timeout_seconds)
    if process.is_alive():
        raise RuntimeStopError("旧推理进程未能退出，已取消加载新模型。")
    self._clear_worker_handles()
```

Call `_start_worker(new_selection)` only after `_stop_worker()` returns successfully. Worker load readiness must use `connection.poll(MODEL_LOAD_TIMEOUT_SECONDS)` and reject EOF, timeout, and malformed messages with structured errors.

- [ ] **Step 5: Implement a session-compatible proxy and batch lease**

The proxy exposes only the method consumed by `task_service.py`:

```python
class RuntimeSessionProxy:
    def remove_background(self, **kwargs):
        return self._manager.call_remove_background(kwargs)
```

`manager.acquire()` increments the lease count only in `ready`, changes visible state to `processing`, and returns an idempotent lease with `.session` and `.close()`. Closing the last lease restores `ready`. `switch()` raises `RuntimeBusyError` when the count is nonzero.

- [ ] **Step 6: Add provider catalog filtering**

```python
def provider_catalog(available: Iterable[str], system_name: str) -> list[dict[str, str]]:
    providers = [{"id": "auto", "label": "自动检测"}]
    if system_name == "Darwin" and "CoreMLExecutionProvider" in available:
        providers.append({"id": "coreml", "label": "Apple CoreML"})
    if "CUDAExecutionProvider" in available:
        providers.append({"id": "cuda", "label": "NVIDIA CUDA"})
    if "CPUExecutionProvider" in available:
        providers.append({"id": "cpu", "label": "CPU"})
    return providers
```

Do not expose `AzureExecutionProvider` because the application has no supported selection path for it.

- [ ] **Step 7: Run focused tests and Ruff**

Run:

```bash
.venv/bin/pytest rmbg_onnx_runner/tests/test_model_manager.py -q
.venv/bin/ruff check rmbg_onnx_runner/model_manager.py rmbg_onnx_runner/tests/test_model_manager.py
```

Expected: all lifecycle tests PASS; fake runtime reports `maximum_live_processes == 1`.

- [ ] **Step 8: Commit**

```bash
git add rmbg_onnx_runner/model_manager.py rmbg_onnx_runner/tests/test_model_manager.py
git commit -m "feat: manage model worker lifecycle"
```

### Task 5: Start Flask without a model and expose runtime APIs

**Files:**
- Modify: `rmbg_onnx_runner/web_app.py`
- Modify: `rmbg_onnx_runner/tests/test_web_app.py`
- Modify: `scripts/start_macos.sh`
- Modify: `scripts/start_linux.sh`
- Modify: `scripts/start_windows.ps1`

- [ ] **Step 1: Replace session-based fixtures with a fake ModelManager**

The fake must implement `status_payload`, `provider_payload`, `start_async`, `switch`, `acquire`, and `close`. Add tests asserting:

```python
def test_app_starts_when_models_directory_is_empty(empty_client):
    response = empty_client.get("/api/status")
    assert response.status_code == 200
    assert response.get_json()["runtimeState"] == "no_model"


def test_runtime_select_returns_409_while_processing(client, fake_manager):
    fake_manager.raise_busy = True
    response = client.post(
        "/api/runtime/select",
        json={"model": "model_fp16.onnx", "provider": "cpu"},
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "RUNTIME_BUSY"


def test_successful_runtime_select_persists_model(client, preferences_path):
    response = client.post(
        "/api/runtime/select",
        json={"model": "selected.onnx", "provider": "cpu"},
    )
    assert response.status_code == 200
    assert load_last_model(preferences_path) == "selected.onnx"
```

- [ ] **Step 2: Run the focused web tests and verify failures**

Run: `.venv/bin/pytest rmbg_onnx_runner/tests/test_web_app.py -q`

Expected: FAIL where `WebAppState` still requires `model_path` and `session`, and where the new endpoints are missing.

- [ ] **Step 3: Replace `WebAppState.session` with `WebAppState.runtime`**

The state contract becomes:

```python
@dataclass
class WebAppState:
    output_root: Path
    runtime: ModelManager
    access_token: str
    server_origin: str
    models_dir: Path = MODELS_DIR
    preferences_path: Path | None = None
    history_retention_days: int = 30
    history_max_tasks: int = 100
    history_keep_latest: int = 10
```

`load_state` creates directories, resolves a nullable startup model, creates `ModelManager`, and returns without constructing `RmbgSession`. `main` creates the Flask app, starts the initial runtime load on a daemon management thread, registers `runtime.close` with `atexit`, then enters Waitress.

- [ ] **Step 4: Add actionable no-model terminal output**

When discovery returns no models, print exactly these facts before serving:

```text
No compatible ONNX model was found.
Models directory: <absolute models directory>
Download RMBG-2.0 ONNX models: https://huggingface.co/briaai/RMBG-2.0/tree/main/onnx
Place one or more .onnx files in the models directory, then refresh the page.
Review the model license before use.
```

Do not automatically download gated model weights.

- [ ] **Step 5: Implement status, provider, and unified selection APIs**

Keep `GET /api/models`, replace direct Session creation in `/api/models/select`, and add `POST /api/runtime/select`. Either keep `/api/models/select` as a compatibility wrapper around the new handler for one release or update every caller and test in the same commit; do not leave two independent switch implementations.

Map manager errors:

```python
except RuntimeBusyError as exc:
    return jsonify(code="RUNTIME_BUSY", error=str(exc)), 409
except RuntimeLoadError as exc:
    return jsonify(exc.to_payload()), 400
except RuntimeStopError as exc:
    return jsonify(code="RUNTIME_STOP_FAILED", error=str(exc)), 500
```

Persist the model only after `runtime.switch()` returns success.

- [ ] **Step 6: Forward the controlled memory-pattern option**

Add:

```python
parser.add_argument(
    "--disable-mem-pattern",
    action="store_true",
    help="Disable ONNX Runtime memory-pattern reuse for measurement or constrained environments.",
)
```

Forward it through `RuntimeSelection`. The platform start scripts keep the default and must not add this flag automatically.

- [ ] **Step 7: Verify startup scripts only launch the web control plane**

The scripts may continue executing `web_app.py`, but they must not invoke `check_env.py`, `run_rmbg_onnx.py`, or pass a fixed model. Preserve `--models-dir`, `--output-dir`, `--provider auto`, and user-supplied trailing arguments.

- [ ] **Step 8: Run web and repository tests**

Run:

```bash
.venv/bin/pytest rmbg_onnx_runner/tests/test_web_app.py rmbg_onnx_runner/tests/test_repository.py -q
.venv/bin/python rmbg_onnx_runner/web_app.py --help
```

Expected: PASS; help includes `--disable-mem-pattern`; constructing app state with an empty models directory does not import or instantiate ONNX Runtime.

- [ ] **Step 9: Commit scoped changes**

```bash
git diff -- rmbg_onnx_runner/web_app.py rmbg_onnx_runner/tests/test_web_app.py scripts/start_macos.sh scripts/start_linux.sh scripts/start_windows.ps1
git add -p rmbg_onnx_runner/web_app.py rmbg_onnx_runner/tests/test_web_app.py
git add scripts/start_macos.sh scripts/start_linux.sh scripts/start_windows.ps1
git commit -m "feat: start web service without a model"
```

### Task 6: Route complete batches through leases and preserve diagnostic failures

**Files:**
- Modify: `rmbg_onnx_runner/web_app.py`
- Modify: `rmbg_onnx_runner/task_service.py`
- Modify: `rmbg_onnx_runner/tests/test_web_app.py`
- Modify: `rmbg_onnx_runner/tests/test_task_service.py`

- [ ] **Step 1: Write failing lease-lifetime and OOM payload tests**

For both JSON and NDJSON responses, assert one lease is acquired before the first event and released after `done` or after generator failure. Add this worker failure fixture:

```python
class OutOfMemorySession:
    def remove_background(self, **_kwargs):
        raise RuntimeInvocationError(
            {
                "code": "SYSTEM_OUT_OF_MEMORY",
                "stage": "inference",
                "reason": "系统可用内存不足，推理未能完成。",
                "detail": "MemoryError: allocation failed",
                "suggestion": "当前可用内存约 768 MiB；请关闭其他应用或改用更小的模型。",
                "confidence": "confirmed",
                "resources": {
                    "availableSystemMemoryBytes": 805306368,
                    "totalSystemMemoryBytes": 8589934592,
                    "processRssBytes": 1073741824,
                    "cudaFreeMemoryBytes": None,
                    "cudaTotalMemoryBytes": None,
                },
            }
        )
```

Assert the item manifest and streamed event retain every field without converting it back to generic `INFERENCE_FAILED`.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/pytest rmbg_onnx_runner/tests/test_task_service.py rmbg_onnx_runner/tests/test_web_app.py -q
```

Expected: failures show the route does not use leases and `task_service` replaces the structured runtime failure.

- [ ] **Step 3: Introduce a narrow session protocol in task service**

```python
class BackgroundRemovalSession(Protocol):
    def remove_background(self, **kwargs) -> rmbg_onnx.RmbgRunResult: ...
```

Change annotations on `process_item` and `iter_process_events` from concrete `RmbgSession` to this protocol. Do not change output file handling or security validation.

- [ ] **Step 4: Preserve structured invocation errors**

Catch `RuntimeInvocationError` before the generic exception branch:

```python
except RuntimeInvocationError as exc:
    item["message"] = exc.payload["reason"]
    item["error"] = dict(exc.payload)
    traceback.print_exc()
    return item, False
```

Generic image, save, and unknown inference failures continue through the existing stage-based classifier, but the inference branch calls `diagnose_runtime_error` to attach a resource snapshot.

- [ ] **Step 5: Hold one lease for the entire response lifecycle**

For JSON, acquire before consuming `iter_process_events` and close in `finally`. For NDJSON, close inside the streaming generator's `finally` block together with uploads:

```python
lease = state.runtime.acquire()
events = iter_process_events(..., session=lease.session, ...)

def lines():
    try:
        for event in events:
            yield json.dumps(event, ensure_ascii=False) + "\n"
    finally:
        lease.close()
        close_uploads(detached_fields)
```

If acquire fails because runtime is loading, switching, absent, or errored, close detached uploads and return 503 with the current runtime state and suggestion.

- [ ] **Step 6: Run tests and lint**

Run:

```bash
.venv/bin/pytest rmbg_onnx_runner/tests/test_task_service.py rmbg_onnx_runner/tests/test_web_app.py -q
.venv/bin/ruff check rmbg_onnx_runner/task_service.py rmbg_onnx_runner/web_app.py
```

Expected: PASS; the fake manager reports zero leases after every response and exception path.

- [ ] **Step 7: Commit scoped hunks**

```bash
git add -p rmbg_onnx_runner/web_app.py rmbg_onnx_runner/task_service.py
git add -p rmbg_onnx_runner/tests/test_web_app.py rmbg_onnx_runner/tests/test_task_service.py
git commit -m "feat: diagnose inference failures"
```

### Task 7: Add provider selection, no-model guidance, and visible runtime feedback

**Files:**
- Modify: `rmbg_onnx_runner/web/index.html`
- Modify: `rmbg_onnx_runner/web/app.js`
- Modify: `rmbg_onnx_runner/web/style.css`
- Modify: `rmbg_onnx_runner/tests/test_web_assets.py`

- [ ] **Step 1: Write failing static asset tests**

Assert the page contains:

```html
<select id="providerSelect" class="model-select" disabled></select>
<div id="modelHelp" class="model-help" hidden>
  <a href="https://huggingface.co/briaai/RMBG-2.0/tree/main/onnx">下载 RMBG-2.0 ONNX 模型</a>
</div>
<div id="runtimeToast" class="runtime-toast" role="status" aria-live="polite" hidden></div>
```

Assert JavaScript fetches `/api/providers` and posts model plus provider to `/api/runtime/select`. Assert it no longer calls `localStorage.getItem("koutu-model")` or `localStorage.setItem("koutu-model", ...)`.

- [ ] **Step 2: Run and verify failures**

Run: `.venv/bin/pytest rmbg_onnx_runner/tests/test_web_assets.py -q`

Expected: FAIL because provider/help/toast elements and unified selection are missing.

- [ ] **Step 3: Add provider and no-model UI**

Keep the existing model selector. Add the provider selector directly below it. Change the hint to `服务会记住上次成功加载的模型`. The help panel must show the models directory returned by the API, the exact Hugging Face ONNX link, placement instructions, and a license reminder.

- [ ] **Step 4: Implement runtime polling and selection**

Add one state-to-copy map:

```javascript
const runtimeStateText = {
  no_model: "未找到可用模型",
  loading: "正在加载模型…",
  ready: "服务已就绪",
  processing: "正在处理图片…",
  switching: "正在切换模型…",
  error: "模型运行环境异常",
  stopped: "模型服务已停止",
};
```

`loadRuntimeControls()` fetches models, providers, and status. `selectRuntime()` sends both selected values, disables both selectors, waits for the response, and on success displays:

```text
模型切换成功：model_fp16.onnx · Apple CoreML · 2.418 秒
```

On HTTP 409, restore both previous values and show `当前有任务正在处理，请完成后再切换模型或推理方式。`

- [ ] **Step 5: Render evidence and confidence for failures**

Add formatter functions for bytes and diagnosis confidence. A failed result displays:

```text
错误类型：系统内存不足（已确认）
错误原因：MemoryError: allocation failed
故障时系统可用内存：768 MiB / 8.0 GiB
故障时进程占用：1.0 GiB
处理建议：关闭其他应用，或改用体积更小的量化模型。
```

Show CUDA free/total memory only when both values are present. Translate `likely` as `可能原因` and `unknown` as `原因未确认`; never display `likely` as confirmed.

- [ ] **Step 6: Style the new states accessibly**

Reuse existing control colors. Add visible focus styles, do not rely only on red/green, keep the help link keyboard accessible, and honor the existing reduced-motion media query for toast transitions.

- [ ] **Step 7: Run asset tests**

Run: `.venv/bin/pytest rmbg_onnx_runner/tests/test_web_assets.py -q`

Expected: PASS, including the removal of browser model persistence and presence of `aria-live="polite"`.

- [ ] **Step 8: Commit scoped frontend changes**

```bash
git diff -- rmbg_onnx_runner/web/index.html rmbg_onnx_runner/web/app.js rmbg_onnx_runner/web/style.css rmbg_onnx_runner/tests/test_web_assets.py
git add -p rmbg_onnx_runner/web/index.html rmbg_onnx_runner/web/app.js rmbg_onnx_runner/web/style.css rmbg_onnx_runner/tests/test_web_assets.py
git commit -m "feat: expose model runtime controls"
```

### Task 8: Document behavior and complete verification

**Files:**
- Modify: `README.md`
- Modify: `rmbg_onnx_runner/README.md`
- Modify: `rmbg_onnx_runner/tests/test_repository.py`

- [ ] **Step 1: Update repository tests for the public contract**

Require these strings or equivalent verified links in public documentation:

```python
assert "https://huggingface.co/briaai/RMBG-2.0/tree/main/onnx" in readme
assert "独立推理进程" in readme
assert "Apple CoreML" in readme
assert "--disable-mem-pattern" in readme
assert "故障时可用内存" in readme
```

- [ ] **Step 2: Run and verify the documentation test fails**

Run: `.venv/bin/pytest rmbg_onnx_runner/tests/test_repository.py -q`

Expected: FAIL until the documentation is updated.

- [ ] **Step 3: Document lifecycle and recovery behavior**

Document:

```text
启动脚本只启动本地 Web 管理服务。模型运行在独立推理进程中。
切换模型或推理方式时，系统先确认旧推理进程退出，再启动新进程。
切换期间不接受新任务；已有任务不会被强制终止。
如果新模型加载失败，系统会尝试重新启动原模型。
```

Also document no-model recovery, exact model path/link/license, Provider meanings, error confidence, system/GPU memory snapshots, and the fact that CoreML does not guarantee GPU-only or ANE-only execution.

- [ ] **Step 4: Document the memory-pattern decision and measurement procedure**

State that memory patterns remain enabled by default. Provide two equivalent commands using the same model, provider, and input set:

```bash
./scripts/start_macos.sh --provider cpu
./scripts/start_macos.sh --provider cpu --disable-mem-pattern
```

Record startup RSS, first-inference peak, steady RSS after ten identical-size images, and total processing time. Change the default only if a repeatable memory improvement justifies the measured latency regression; do not use Python `tracemalloc` as proof because it excludes ONNX Runtime native allocations.

- [ ] **Step 5: Run the complete automated verification**

Run from the repository root:

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/python rmbg_onnx_runner/web_app.py --help
```

Expected: all tests PASS, Ruff exits 0, and CLI help exits 0.

- [ ] **Step 6: Perform real runtime smoke tests without committing generated data**

With `models/model_fp16.onnx` present:

1. Start the app and confirm the browser becomes available while status is `loading`.
2. Confirm status becomes `ready` and reports the actual Provider.
3. Process one image and confirm the worker PID remains stable.
4. Switch Provider or model and record the old PID.
5. Confirm the old PID no longer exists before the new worker reports `ready`.
6. Start a batch and attempt a switch from another browser tab; confirm HTTP 409 and no task interruption.
7. Stop the service and confirm the worker PID exits.

Move the model out of `models/` using a reversible temporary location, start the app, confirm the UI shows the download guidance, then restore the model. Do not delete the model and do not commit `outputs/`.

- [ ] **Step 7: Exercise failure diagnostics proportionally to available hardware**

- CPU: inject a test-only `MemoryError` through the fake worker and verify available/total memory and process RSS appear.
- CUDA host: use a controlled test double for automated tests; do not intentionally exhaust production GPU memory. Verify the `nvidia-smi` parser against normal command output and confirm unavailable `nvidia-smi` leaves CUDA fields null.
- CoreML host: confirm the UI reports system/unified memory only and does not invent a separate VRAM value.
- Invalid model: copy a small invalid `.onnx` fixture into a temporary models directory and confirm `MODEL_LOAD_FAILED`, rollback state, and a non-claiming confidence value.

- [ ] **Step 8: Review the complete diff and commit documentation/tests**

```bash
git diff --check
git status --short
git diff -- README.md rmbg_onnx_runner/README.md rmbg_onnx_runner/tests/test_repository.py
git add -p README.md rmbg_onnx_runner/README.md rmbg_onnx_runner/tests/test_repository.py
git commit -m "docs: explain model runtime management"
```

## Final acceptance checklist

- [ ] Flask/Waitress serves the UI with zero models and does not instantiate ONNX Runtime in the web process.
- [ ] The terminal and browser show the absolute models directory, exact ONNX download link, placement instructions, and license warning.
- [ ] Explicit `--model` wins; otherwise a valid saved model wins; otherwise the first sorted model wins.
- [ ] A model choice is persisted only after worker readiness and does not cause a second browser-triggered startup switch.
- [ ] Model and Provider switches use one unified request and show success only after readiness.
- [ ] Runtime status distinguishes `no_model`, `loading`, `ready`, `processing`, `switching`, `error`, and `stopped`.
- [ ] A switch cannot begin while a batch lease exists.
- [ ] The old worker is confirmed dead before the new worker starts; tests prove maximum live worker count is one.
- [ ] A failed replacement attempts sequential rollback and reports whether restoration succeeded.
- [ ] Process shutdown escalates from graceful stop to terminate/kill with bounded waits and never starts a replacement while the old process is alive.
- [ ] Provider choices come from installed ONNX Runtime providers and use truthful labels.
- [ ] OOM errors include fault-time system memory; CUDA OOM includes GPU memory only when it can be measured.
- [ ] Diagnostic confidence prevents text-based guesses from being presented as confirmed facts.
- [ ] Existing Host/Origin/token/header/path protections and task history behavior still pass tests.
- [ ] Memory patterns remain enabled by default; the optional flag is documented as a measurement knob.
- [ ] Full pytest, Ruff, CLI smoke test, and real worker-PID lifecycle smoke test pass.
