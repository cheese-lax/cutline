from pathlib import Path
import unittest


RUNNER_DIR = Path(__file__).resolve().parents[1]


class WebAssetTests(unittest.TestCase):
    def test_preview_images_use_contain_sizing_inside_stable_stage(self):
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn("aspect-ratio:", css)
        self.assertIn(".image-stage img", css)
        self.assertIn("width: 100%;", css)
        self.assertIn("height: 100%;", css)
        self.assertIn("object-fit: contain;", css)

    def test_frontend_requests_streaming_process_results(self):
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("application/x-ndjson", script)
        self.assertIn("readProcessStream", script)
        self.assertIn("appendResult", script)

    def test_frontend_exposes_output_settings_without_footer_status_bar(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('name="outputFormat"', markup)
        self.assertIn('id="edgeOptimize"', markup)
        self.assertIn('id="transparentBackground"', markup)
        self.assertIn('id="backgroundColor"', markup)
        self.assertIn('form.append("outputFormat"', script)
        self.assertIn('form.append("backgroundColor"', script)
        self.assertIn("function resetSettings", script)
        self.assertNotIn("selectAllBtn", script)
        self.assertNotIn("全选", markup)
        self.assertNotIn("显存", markup)
        self.assertNotIn("版本", markup)

    def test_frontend_exposes_line_art_mode_and_submits_it(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('name="processingMode"', markup)
        self.assertIn('value="line_art"', markup)
        self.assertIn("自动识别背景色", markup)
        self.assertIn('form.append("processingMode"', script)
        self.assertIn("selectedProcessingMode", script)

    def test_processing_mode_matches_full_width_purple_segmented_control(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('class="field-label mode-label"', markup)
        self.assertIn('class="mode-info"', markup)
        self.assertIn('class="segmented processing-mode-control"', markup)
        self.assertIn(".processing-mode-control", css)
        self.assertIn(".segmented input:focus-visible + span", css)
        self.assertIn("自动识别背景色并按灰度差生成透明度", script)

    def test_completed_batch_items_can_be_selected_for_comparison(self):
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn("selectedIndex", script)
        self.assertIn("function selectResult", script)
        self.assertIn("data-index", script)
        self.assertIn('aria-selected", String(isSelected)', script)
        self.assertIn("syncSelectedPreview", script)
        self.assertIn(".result-card.is-selected", css)

    def test_frontend_opens_current_run_and_restores_recent_task(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("打开本次结果文件夹", markup)
        self.assertIn("currentRunId", script)
        self.assertIn("function openCurrentRunFolder", script)
        self.assertIn("/api/open-output?runId=", script)
        self.assertIn("function loadRecentTask", script)
        self.assertIn("/api/tasks/recent?limit=1", script)
        self.assertIn("inputUrl", script)


if __name__ == "__main__":
    unittest.main()
