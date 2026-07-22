import io
import json
import tempfile
from datetime import datetime, timezone
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


class FailingSession:
    def remove_background(self, input_path, output_path, **options):
        raise RuntimeError("provider execution failed")


def upload(name="first.png", data=b"image"):
    return FileStorage(stream=io.BytesIO(data), filename=name, content_type="image/png")


def test_options_from_form_preserves_existing_defaults():
    options = task_service.options_from_form(MultiDict())

    assert options == task_service.ProcessOptions()


def test_supported_image_extensions_cover_common_pillow_raster_formats():
    supported_names = [
        "photo.jfif",
        "animation.gif",
        "modern.avif",
        "scan.jp2",
        "texture.tga",
        "icon.ico",
        "source.psd",
        "portable.ppm",
        "compact.qoi",
    ]

    assert all(task_service.is_supported_image(Path(name)) for name in supported_names)
    assert not task_service.is_supported_image(Path("document.pdf"))


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


def test_new_run_id_includes_milliseconds_and_random_suffix():
    run_id = task_service.new_run_id(
        now=datetime(2026, 7, 22, 12, 15, 30, 456000),
        suffix="a1b2",
    )

    assert run_id == "20260722-121530-456-a1b2"


def test_history_preview_only_selects_expired_or_excess_completed_tasks(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    task_specs = [
        ("20260601-120000", "2026-06-01 12:00:00", "done", 11),
        ("20260719-120000", "2026-07-19 12:00:00", "done", 12),
        ("20260720-120000", "2026-07-20 12:00:00", "done", 13),
        ("20260721-120000", "2026-07-21 12:00:00", "done", 14),
        ("20260722-120000", "2026-07-22 12:00:00", "running", 15),
    ]
    for run_id, created_at, status, payload_size in task_specs:
        run_dir = root / run_id
        (run_dir / "results").mkdir(parents=True)
        (run_dir / "results" / "result.png").write_bytes(b"x" * payload_size)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "runId": run_id,
                    "createdAt": created_at,
                    "status": status,
                }
            ),
            encoding="utf-8",
        )
    (root / "notes").mkdir()
    (root / "notes" / "keep.txt").write_text("keep", encoding="utf-8")
    (root / "broken").mkdir()
    (root / "broken" / "manifest.json").write_text("not json", encoding="utf-8")

    preview = task_service.task_history_summary(
        root,
        retention_days=30,
        max_tasks=2,
        keep_latest=1,
        protected_run_ids={"20260720-120000"},
        now=datetime(2026, 7, 22, 16, 0, tzinfo=timezone.utc),
    )

    assert preview["totalTasks"] == 5
    assert preview["cleanupTasks"] == 2
    assert preview["cleanupRunIds"] == ["20260601-120000", "20260719-120000"]
    assert preview["skippedRunning"] == 1
    assert preview["totalBytes"] >= sum(spec[3] for spec in task_specs)
    assert preview["cleanupBytes"] > 0
    assert preview["oldestAt"] == "2026-06-01 12:00:00"
    assert preview["newestAt"] == "2026-07-22 12:00:00"


def test_cleanup_task_history_deletes_previewed_tasks_and_preserves_other_entries(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    for run_id, created_at in [
        ("20260601-120000", "2026-06-01 12:00:00"),
        ("20260722-120000", "2026-07-22 12:00:00"),
    ]:
        run_dir = root / run_id
        run_dir.mkdir()
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
    unrelated = root / "notes"
    unrelated.mkdir()
    (unrelated / "keep.txt").write_text("keep", encoding="utf-8")

    result = task_service.cleanup_task_history(
        root,
        retention_days=30,
        max_tasks=100,
        keep_latest=1,
        now=datetime(2026, 7, 22, 16, 0, tzinfo=timezone.utc),
    )

    assert result["deletedTasks"] == 1
    assert result["freedBytes"] > 0
    assert result["remainingTasks"] == 1
    assert not (root / "20260601-120000").exists()
    assert (root / "20260722-120000").is_dir()
    assert (unrelated / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_list_task_history_returns_newest_metadata_and_delete_permissions(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    for run_id, created_at, status, total in [
        ("20260721-120000", "2026-07-21 12:00:00", "done", 2),
        ("20260722-120000", "2026-07-22 12:00:00", "running", 3),
    ]:
        run_dir = root / run_id
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "runId": run_id,
                    "createdAt": created_at,
                    "status": status,
                    "total": total,
                    "success": total - 1,
                    "failed": 1,
                    "items": [{"inputName": "should-not-be-in-list.png"}],
                }
            ),
            encoding="utf-8",
        )

    tasks = task_service.list_task_history(
        root,
        protected_run_ids={"20260721-120000"},
        now=datetime(2026, 7, 22, 16, 0, tzinfo=timezone.utc),
    )

    assert [task["runId"] for task in tasks] == ["20260722-120000", "20260721-120000"]
    assert tasks[0]["status"] == "running"
    assert tasks[0]["canDelete"] is False
    assert tasks[1]["canDelete"] is False
    assert tasks[1]["total"] == 2
    assert "items" not in tasks[1]


def test_load_task_for_run_rejects_invalid_id_and_returns_manifest(tmp_path):
    root = tmp_path / "outputs"
    run_dir = root / "20260722-120000"
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "runId": "20260722-120000",
                "status": "done",
                "items": [{"inputName": "first.png"}],
            }
        ),
        encoding="utf-8",
    )

    assert task_service.load_task_for_run(root, "20260722-120000")["items"][0][
        "inputName"
    ] == "first.png"
    assert task_service.load_task_for_run(root, "../secret") is None


def test_delete_task_history_deletes_selected_valid_tasks_only(tmp_path):
    root = tmp_path / "outputs"
    root.mkdir()
    for run_id, status in [
        ("old", "done"),
        ("protected", "done"),
        ("active", "running"),
    ]:
        run_dir = root / run_id
        run_dir.mkdir()
        (run_dir / "manifest.json").write_text(
            json.dumps({"schemaVersion": 1, "runId": run_id, "status": status}),
            encoding="utf-8",
        )
    unrelated = root / "notes"
    unrelated.mkdir()

    result = task_service.delete_task_history(
        root,
        ["old", "old", "protected", "active", "../secret", "notes"],
        protected_run_ids={"protected"},
    )

    assert result["deletedRunIds"] == ["old"]
    assert result["deletedTasks"] == 1
    assert set(result["skippedRunIds"]) == {"protected", "active", "../secret", "notes"}
    assert not (root / "old").exists()
    assert (root / "protected").is_dir()
    assert (root / "active").is_dir()
    assert unrelated.is_dir()


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
    assert events[1]["item"]["error"]["suggestion"] == (
        "请选择 JPG、PNG、WEBP、静态 AVIF、BMP、单页 TIFF、ICO 或 TGA 图片。"
    )
    assert events[2]["item"]["ok"] is True
    assert events[-1]["success"] == 1
    assert events[-1]["failed"] == 1


def test_failed_item_includes_structured_stage_reason_and_suggestion():
    with tempfile.TemporaryDirectory() as tmpdir:
        events = list(
            task_service.iter_process_events(
                fields=[upload("broken.png")],
                relative_paths=["broken.png"],
                output_root=Path(tmpdir),
                session=FailingSession(),
                run_id="20260722-124000",
            )
        )

    error = events[1]["item"]["error"]
    assert error["code"] == "INFERENCE_FAILED"
    assert error["stage"] == "模型处理"
    assert error["reason"] == "模型未能完成这张图片的处理。"
    assert error["detail"] == "RuntimeError: provider execution failed"
    assert "重试" in error["suggestion"]
