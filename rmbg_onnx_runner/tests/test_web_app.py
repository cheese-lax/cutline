import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import web_app


class FakeUploadField:
    def __init__(self, filename: str, data: bytes):
        self.filename = filename
        self.file = io.BytesIO(data)


class FakeSession:
    def __init__(self):
        self.calls = []

    def remove_background(self, input_path, output_path, **options):
        self.calls.append((Path(input_path), Path(output_path), options))
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"result")
        return SimpleNamespace(inference_seconds=0.12)


def png_bytes() -> bytes:
    return b"image"


class WebAppProcessingTests(unittest.TestCase):
    def test_process_upload_events_emit_each_item_before_done(self):
        fields = [
            FakeUploadField("first.png", png_bytes()),
            FakeUploadField("second.png", png_bytes()),
        ]
        session = FakeSession()

        with tempfile.TemporaryDirectory() as tmpdir:
            events = web_app.iter_process_events(
                fields=fields,
                relative_paths=["folder/first.png", "folder/second.png"],
                output_root=Path(tmpdir),
                session=session,
                run_id="20260702-120000",
            )

            start = next(events)
            self.assertEqual(start["type"], "start")
            self.assertEqual(start["total"], 2)

            first = next(events)
            self.assertEqual(first["type"], "item")
            self.assertEqual(first["index"], 1)
            self.assertEqual(first["success"], 1)
            self.assertTrue(first["item"]["ok"])
            self.assertTrue((Path(tmpdir) / "20260702-120000" / "results" / "folder" / "first_rmbg.png").exists())

            second = next(events)
            self.assertEqual(second["type"], "item")
            self.assertEqual(second["index"], 2)
            self.assertEqual(second["success"], 2)

            done = next(events)
            self.assertEqual(done["type"], "done")
            self.assertEqual(done["success"], 2)
            self.assertEqual(done["failed"], 0)
            self.assertEqual(len(done["items"]), 2)

            with self.assertRaises(StopIteration):
                next(events)

    def test_process_upload_events_pass_output_options_to_session(self):
        fields = [FakeUploadField("first.png", png_bytes())]
        session = FakeSession()

        with tempfile.TemporaryDirectory() as tmpdir:
            events = list(
                web_app.iter_process_events(
                    fields=fields,
                    relative_paths=["first.png"],
                    output_root=Path(tmpdir),
                    session=session,
                    run_id="20260702-120000",
                    options=web_app.ProcessOptions(
                        processing_mode="line_art",
                        output_format="webp",
                        edge_optimize=True,
                        transparent_background=False,
                        background_color="#ffeecc",
                    ),
                )
            )

        item = events[1]["item"]
        self.assertEqual(item["outputName"], "first_lineart.webp")
        self.assertEqual(session.calls[0][2]["processing_mode"], "line_art")
        self.assertEqual(session.calls[0][2]["output_format"], "webp")
        self.assertEqual(session.calls[0][2]["edge_optimize"], True)
        self.assertEqual(session.calls[0][2]["transparent_background"], False)
        self.assertEqual(session.calls[0][2]["background_color"], "#ffeecc")

    def test_line_art_mode_uses_distinct_output_name_and_manifest_option(self):
        fields = [FakeUploadField("drawing.png", png_bytes())]
        session = FakeSession()

        with tempfile.TemporaryDirectory() as tmpdir:
            events = list(
                web_app.iter_process_events(
                    fields=fields,
                    relative_paths=["drawing.png"],
                    output_root=Path(tmpdir),
                    session=session,
                    run_id="20260722-120000",
                    options=web_app.ProcessOptions(processing_mode="line_art"),
                )
            )
            manifest = json.loads(
                (Path(tmpdir) / "20260722-120000" / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(events[1]["item"]["outputName"], "drawing_lineart.png")
        self.assertEqual(manifest["options"]["processingMode"], "line_art")

    def test_process_upload_events_write_recoverable_task_manifest(self):
        fields = [FakeUploadField("first.png", png_bytes())]
        session = FakeSession()

        with tempfile.TemporaryDirectory() as tmpdir:
            events = list(
                web_app.iter_process_events(
                    fields=fields,
                    relative_paths=["folder/first.png"],
                    output_root=Path(tmpdir),
                    session=session,
                    run_id="20260702-121500",
                    options=web_app.ProcessOptions(
                        output_format="webp",
                        edge_optimize=True,
                        transparent_background=False,
                        background_color="#ffffff",
                    ),
                )
            )
            manifest_path = Path(tmpdir) / "20260702-121500" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["runId"], "20260702-121500")
        self.assertEqual(manifest["status"], "done")
        self.assertEqual(manifest["total"], 1)
        self.assertEqual(manifest["success"], 1)
        self.assertEqual(manifest["failed"], 0)
        self.assertEqual(manifest["options"]["outputFormat"], "webp")
        self.assertEqual(manifest["options"]["transparentBackground"], False)
        self.assertEqual(manifest["items"][0]["inputName"], "folder/first.png")
        self.assertEqual(manifest["items"][0]["outputName"], "first_rmbg.webp")
        self.assertEqual(manifest["items"][0]["inputUrl"], "/outputs/20260702-121500/_uploads/folder/first.png")
        self.assertEqual(manifest["items"][0]["outputUrl"], "/outputs/20260702-121500/results/folder/first_rmbg.webp")

    def test_load_recent_tasks_returns_newest_manifest_first(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for run_id in ["20260702-120000", "20260702-121500"]:
                run_dir = root / run_id
                run_dir.mkdir()
                (run_dir / "manifest.json").write_text(
                    json.dumps(
                        {
                            "schemaVersion": 1,
                            "runId": run_id,
                            "createdAt": run_id,
                            "updatedAt": run_id,
                            "status": "done",
                            "total": 1,
                            "success": 1,
                            "failed": 0,
                            "outputDir": str(run_dir / "results"),
                            "items": [],
                            "options": {},
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

            tasks = web_app.load_recent_tasks(root, limit=2)

        self.assertEqual([task["runId"] for task in tasks], ["20260702-121500", "20260702-120000"])


if __name__ == "__main__":
    unittest.main()
