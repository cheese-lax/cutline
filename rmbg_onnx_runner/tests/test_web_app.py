import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import web_app
from werkzeug.datastructures import FileStorage


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
def app_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        models_dir = root / "models"
        models_dir.mkdir()
        active_model = models_dir / "active.onnx"
        active_model.write_bytes(b"active")
        state = web_app.WebAppState(
            model_path=active_model,
            output_root=root / "outputs",
            provider="cpu",
            session=FakeSession(),
            access_token="test-token",
            server_origin="http://127.0.0.1:8765",
        )
        state.models_dir = models_dir
        state.disable_fallback = False
        yield state


@pytest.fixture
def client(app_state):
    app = web_app.create_app(app_state, max_upload_mb=16)
    app.config.update(TESTING=True, SERVER_NAME="127.0.0.1:8765")
    with app.test_client() as test_client:
        response = test_client.get(
            "/?token=test-token",
            headers={"Host": "127.0.0.1:8765"},
        )
        assert response.status_code == 200
        yield test_client


def test_index_serves_existing_browser_ui(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Cutline" in response.text


def test_cutline_logo_is_available_to_the_browser_ui(client):
    response = client.get("/cutline-logo.png")

    assert response.status_code == 200
    assert response.content_type == "image/png"
    assert response.data.startswith(b"\x89PNG\r\n\x1a\n")


def test_status_preserves_provider_contract(client):
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.get_json()["providerActive"] == ["CPUExecutionProvider"]
    assert response.get_json()["inputShape"] == [1, 3, 1024, 1024]


def test_models_catalog_lists_onnx_files_and_active_model(client, app_state):
    nested = app_state.models_dir / "portraits"
    nested.mkdir()
    (nested / "detail.onnx").write_bytes(b"detail")
    (app_state.models_dir / "ignore.txt").write_text("ignore", encoding="utf-8")

    response = client.get("/api/models")

    assert response.status_code == 200
    assert response.get_json() == {
        "active": "active.onnx",
        "models": [
            {"id": "active.onnx", "name": "active.onnx", "sizeBytes": 6},
            {
                "id": "portraits/detail.onnx",
                "name": "detail.onnx",
                "sizeBytes": 6,
            },
        ],
    }


def test_select_model_replaces_session_after_success(client, app_state, monkeypatch):
    selected = app_state.models_dir / "selected.onnx"
    selected.write_bytes(b"selected")
    created = []

    class ReplacementSession(FakeSession):
        def __init__(self, model_path, provider, disable_fallback):
            created.append((model_path, provider, disable_fallback))

    monkeypatch.setattr(web_app.rmbg_onnx, "RmbgSession", ReplacementSession)

    response = client.post("/api/models/select", json={"model": "selected.onnx"})

    assert response.status_code == 200
    assert response.get_json()["active"] == "selected.onnx"
    assert created == [(selected.resolve(), "cpu", False)]
    assert app_state.model_path == selected.resolve()
    assert isinstance(app_state.session, ReplacementSession)


def test_select_model_rejects_paths_outside_models_directory(client, app_state, monkeypatch):
    outside = app_state.models_dir.parent / "outside.onnx"
    outside.write_bytes(b"outside")
    created = []
    monkeypatch.setattr(
        web_app.rmbg_onnx,
        "RmbgSession",
        lambda **kwargs: created.append(kwargs),
    )

    response = client.post("/api/models/select", json={"model": "../outside.onnx"})

    assert response.status_code == 400
    assert "models" in response.get_json()["error"]
    assert created == []
    assert app_state.model_path.name == "active.onnx"


def test_process_streams_ndjson(client):
    response = client.post(
        "/api/process",
        data={
            "processingMode": "rmbg",
            "outputFormat": "png",
            "files": (io.BytesIO(b"image"), "first.png"),
            "paths": "folder/first.png",
        },
        headers={"Accept": "application/x-ndjson"},
    )
    events = [json.loads(line) for line in response.text.splitlines()]

    assert response.status_code == 200
    assert [event["type"] for event in events] == ["start", "item", "done"]
    assert events[1]["item"]["inputName"] == "folder/first.png"


def test_detached_upload_survives_request_stream_closing():
    original = FileStorage(
        stream=io.BytesIO(b"image"),
        filename="first.png",
        content_type="image/png",
    )

    detached = web_app.detach_uploads([original])
    original.close()
    try:
        assert detached[0].stream.read() == b"image"
        assert detached[0].filename == "first.png"
    finally:
        web_app.close_uploads(detached)


def test_process_returns_final_json_without_stream_accept(client):
    response = client.post(
        "/api/process",
        data={
            "processingMode": "line_art",
            "files": (io.BytesIO(b"image"), "drawing.png"),
            "paths": "drawing.png",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["success"] == 1
    assert response.get_json()["items"][0]["outputName"] == "drawing_lineart.png"


def test_process_rejects_missing_files(client):
    response = client.post("/api/process", data={"processingMode": "rmbg"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "请上传图片文件。"


def test_recent_tasks_returns_latest_manifest(client, app_state):
    for run_id in ["20260722-120000", "20260722-121500"]:
        run_dir = app_state.output_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(
            json.dumps({"schemaVersion": 1, "runId": run_id}),
            encoding="utf-8",
        )

    response = client.get("/api/tasks/recent?limit=1")

    assert response.status_code == 200
    assert response.get_json()["latest"]["runId"] == "20260722-121500"


def test_history_preview_and_confirmed_cleanup(client, app_state):
    app_state.history_retention_days = 30
    app_state.history_max_tasks = 100
    app_state.history_keep_latest = 1
    for run_id, created_at in [
        ("20240101-120000", "2024-01-01 12:00:00"),
        ("20260722-121500", "2026-07-22 12:15:00"),
    ]:
        run_dir = app_state.output_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "runId": run_id,
                    "createdAt": created_at,
                    "status": "done",
                }
            ),
            encoding="utf-8",
        )

    preview = client.get("/api/tasks/history?protectRunId=20260722-121500")
    rejected = client.post("/api/tasks/cleanup", json={})
    cleaned = client.post(
        "/api/tasks/cleanup",
        json={"confirm": True, "protectRunId": "20260722-121500"},
    )

    assert preview.status_code == 200
    assert preview.get_json()["cleanupTasks"] == 1
    assert preview.get_json()["policy"] == {
        "retentionDays": 30,
        "maxTasks": 100,
        "keepLatest": 1,
    }
    assert rejected.status_code == 400
    assert "确认" in rejected.get_json()["error"]
    assert cleaned.status_code == 200
    assert cleaned.get_json()["deletedTasks"] == 1
    assert not (app_state.output_root / "20240101-120000").exists()
    assert (app_state.output_root / "20260722-121500").is_dir()


def test_task_management_lists_views_and_batch_deletes_history(client, app_state):
    for run_id, created_at in [
        ("20260720-120000", "2026-07-20 12:00:00"),
        ("20260721-120000", "2026-07-21 12:00:00"),
    ]:
        run_dir = app_state.output_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "runId": run_id,
                    "createdAt": created_at,
                    "status": "done",
                    "total": 1,
                    "success": 1,
                    "failed": 0,
                    "items": [{"inputName": f"{run_id}.png"}],
                }
            ),
            encoding="utf-8",
        )

    history = client.get("/api/tasks/history?protectRunId=20260721-120000")
    detail = client.get("/api/tasks/20260720-120000")
    rejected = client.post("/api/tasks/delete", json={"runIds": ["20260720-120000"]})
    deleted = client.post(
        "/api/tasks/delete",
        json={
            "confirm": True,
            "runIds": ["20260720-120000", "20260721-120000"],
            "protectRunId": "20260721-120000",
        },
    )

    assert history.status_code == 200
    assert [task["runId"] for task in history.get_json()["tasks"]] == [
        "20260721-120000",
        "20260720-120000",
    ]
    assert history.get_json()["tasks"][0]["canDelete"] is False
    assert detail.status_code == 200
    assert detail.get_json()["task"]["items"][0]["inputName"] == "20260720-120000.png"
    assert rejected.status_code == 400
    assert deleted.status_code == 200
    assert deleted.get_json()["deletedRunIds"] == ["20260720-120000"]
    assert (app_state.output_root / "20260721-120000").is_dir()


def test_cleanup_history_accepts_seven_day_quick_rule(client, app_state):
    for run_id, created_at in [
        ("20260701-120000", "2026-07-01 12:00:00"),
        ("20260720-120000", "2026-07-20 12:00:00"),
    ]:
        run_dir = app_state.output_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "runId": run_id,
                    "createdAt": created_at,
                    "status": "done",
                }
            ),
            encoding="utf-8",
        )

    response = client.post(
        "/api/tasks/cleanup",
        json={"confirm": True, "olderThanDays": 7},
    )

    assert response.status_code == 200
    assert response.get_json()["policy"]["retentionDays"] == 7
    assert not (app_state.output_root / "20260701-120000").exists()
    assert (app_state.output_root / "20260720-120000").is_dir()


def test_cleanup_history_rejects_unknown_quick_rule(client):
    response = client.post(
        "/api/tasks/cleanup",
        json={"confirm": True, "olderThanDays": 14},
    )

    assert response.status_code == 400
    assert "7" in response.get_json()["error"]
    assert "30" in response.get_json()["error"]


def test_parser_defaults_to_manual_history_cleanup():
    args = web_app.build_parser().parse_args([])

    assert args.models_dir == str(web_app.MODELS_DIR)
    assert args.model is None
    assert args.history_days == 30
    assert args.history_max_tasks == 100
    assert args.history_keep_latest == 10
    assert args.auto_cleanup is False


def test_load_state_rejects_startup_model_outside_models_directory(tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    outside = tmp_path / "outside.onnx"
    outside.write_bytes(b"outside")
    created = []
    monkeypatch.setattr(
        web_app.rmbg_onnx,
        "RmbgSession",
        lambda **kwargs: created.append(kwargs) or FakeSession(),
    )
    args = web_app.build_parser().parse_args(
        [
            "--models-dir",
            str(models_dir),
            "--model",
            str(outside),
            "--output-dir",
            str(tmp_path / "outputs"),
        ]
    )

    with pytest.raises(ValueError, match="models"):
        web_app.load_state(args)

    assert created == []


def test_outputs_route_serves_only_output_root_files(client, app_state):
    output = app_state.output_root / "run" / "results" / "image.png"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"png")

    response = client.get("/outputs/run/results/image.png")

    assert response.status_code == 200
    assert response.data == b"png"


def test_upload_limit_returns_json(client):
    client.application.config["MAX_CONTENT_LENGTH"] = 4
    response = client.post(
        "/api/process",
        data={"files": (io.BytesIO(b"content"), "large.png")},
    )

    assert response.status_code == 413
    assert "上传内容超过" in response.get_json()["error"]


def test_root_rejects_wrong_token(client):
    with client.application.test_client() as fresh_client:
        response = fresh_client.get(
            "/?token=wrong",
            headers={"Host": "127.0.0.1:8765"},
        )

    assert response.status_code == 403


def test_api_rejects_missing_cookie(client):
    with client.application.test_client() as fresh_client:
        response = fresh_client.get(
            "/api/status",
            headers={"Host": "127.0.0.1:8765"},
        )

    assert response.status_code == 403


def test_rejects_untrusted_host(client):
    response = client.get("/api/status", headers={"Host": "evil.example"})

    assert response.status_code == 403


def test_rejects_cross_origin_post(client):
    response = client.post(
        "/api/process",
        data={"files": (io.BytesIO(b"image"), "first.png")},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403


def test_open_output_is_post_only(client):
    assert client.get("/api/open-output").status_code == 405


def test_open_output_opens_only_selected_run(client, app_state, monkeypatch):
    target = app_state.output_root / "20260722-130000" / "results"
    target.mkdir(parents=True)
    opened = []
    monkeypatch.setattr(web_app, "open_in_file_manager", opened.append)

    response = client.post(
        "/api/open-output",
        json={"runId": "20260722-130000"},
    )

    assert response.status_code == 200
    assert opened == [target.resolve()]


def test_open_output_rejects_parent_path(client):
    response = client.post("/api/open-output", json={"runId": "../secret"})

    assert response.status_code == 400


def test_open_result_rejects_path_outside_output_root(client, tmp_path):
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"image")

    response = client.post("/api/open-result", json={"path": str(outside)})

    assert response.status_code == 400


def test_secure_headers_are_present(client):
    response = client.get("/api/status")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
