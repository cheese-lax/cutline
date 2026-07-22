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
def app_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        yield web_app.WebAppState(
            model_path=root / "model.onnx",
            output_root=root / "outputs",
            provider="cpu",
            session=FakeSession(),
            access_token="test-token",
            server_origin="http://127.0.0.1:8765",
        )


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
    assert "一键抠图" in response.text


def test_status_preserves_provider_contract(client):
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.get_json()["providerActive"] == ["CPUExecutionProvider"]
    assert response.get_json()["inputShape"] == [1, 3, 1024, 1024]


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
