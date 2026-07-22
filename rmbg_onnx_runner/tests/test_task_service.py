import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import task_service
from werkzeug.datastructures import FileStorage, MultiDict


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
    assert events[1]["item"]["inputUrl"] == "/outputs/20260722-120000/_uploads/folder/first.png"
    assert events[1]["item"]["outputUrl"] == (
        "/outputs/20260722-120000/results/folder/first_rmbg.png"
    )
    assert manifest["status"] == "done"
    assert manifest["success"] == 1


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


def test_safe_relative_path_removes_parent_segments_and_drive_prefixes():
    assert task_service.safe_relative_path("../folder/image.png", "fallback.png") == Path(
        "folder/image.png"
    )
    assert task_service.safe_relative_path("C:/image.png", "fallback.png") == Path("image.png")


def test_failed_item_does_not_stop_remaining_batch():
    session = FakeSession()
    with tempfile.TemporaryDirectory() as tmpdir:
        events = list(
            task_service.iter_process_events(
                fields=[upload("bad.txt"), upload("good.png")],
                relative_paths=["bad.txt", "good.png"],
                output_root=Path(tmpdir),
                session=session,
                run_id="20260722-123000",
            )
        )

    assert events[1]["item"]["ok"] is False
    assert events[2]["item"]["ok"] is True
    assert events[-1]["success"] == 1
    assert events[-1]["failed"] == 1
