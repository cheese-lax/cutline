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
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
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
