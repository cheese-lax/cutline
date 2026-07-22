import re
import unittest
from pathlib import Path

RUNNER_DIR = Path(__file__).resolve().parents[1]


def contrast_ratio(first, second):
    def luminance(value):
        channels = [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


class WebAssetTests(unittest.TestCase):
    def test_frontend_defaults_to_english_and_exposes_a_persistent_language_switcher(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn('<html lang="en">', markup)
        self.assertIn('id="languageSwitcher"', markup)
        self.assertIn('data-language="zh-CN"', markup)
        self.assertIn('data-language="en"', markup)
        self.assertIn('class="language-switcher"', markup)
        self.assertIn("function applyLanguage", script)
        self.assertIn('localStorage.getItem("cutline-language")', script)
        self.assertIn('localStorage.setItem("cutline-language"', script)
        self.assertIn("const translations =", script)
        self.assertIn("en:", script)
        self.assertIn('"zh-CN":', script)
        self.assertIn("initialLanguage()", script)
        self.assertIn("applyLanguage(initialLanguage())", script)
        self.assertIn(".language-switcher", css)

    def test_runtime_options_are_positioned_next_to_the_logo_in_the_topbar(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")

        topbar = markup[markup.index("<header"):markup.index("</header>")]
        side_panel = markup[markup.index('<aside class="side-panel">'):markup.index("</aside>")]

        self.assertIn('class="top-runtime-controls"', topbar)
        self.assertLess(topbar.index("brand-mark"), topbar.index("top-runtime-controls"))
        self.assertLess(topbar.index("top-runtime-controls"), topbar.index("top-actions"))
        self.assertIn('id="modelSelect"', topbar)
        self.assertIn('id="providerSelect"', topbar)
        self.assertIn('name="processingMode"', topbar)
        self.assertNotIn('id="modelSelect"', side_panel)

    def test_side_panel_keeps_process_button_in_a_dedicated_bottom_section(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn('class="panel-block settings-actions"', markup)
        self.assertRegex(
            css,
            r"\.side-panel\s*\{[^}]*display:\s*grid;[^}]*grid-template-rows:\s*minmax\(0, 2fr\) minmax\(0, 2fr\) minmax\(0, 1fr\);",
        )
        self.assertRegex(css, r"\.settings-panel\s*\{[^}]*overflow-y:\s*auto;")
        self.assertRegex(css, r"\.settings-actions\s*\{[^}]*justify-content:\s*center;")

    def test_original_preview_is_an_image_drop_target(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn('id="originalUploadZone"', markup)
        self.assertIn('id="originalEmpty" data-i18n="dragOrPaste">Drag or paste an image here', markup)
        self.assertIn("originalUploadZone: document.querySelector", script)
        self.assertIn("bindImageDropTarget(els.originalUploadZone)", script)
        self.assertIn(".upload-target.dragging", css)

    def test_frontend_accepts_clipboard_image_files(self):
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("function clipboardImageFiles", script)
        self.assertIn('document.addEventListener("paste", handleImagePaste)', script)
        self.assertIn("event.clipboardData", script)
        self.assertIn("setFiles(files)", script)

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
        self.assertIn('name="outputFormat" value="jpg"', markup)
        self.assertIn('name="outputFormat" value="avif"', markup)
        claim = re.search(
            r'<strong data-i18n="uploadSingle">Upload one image</strong>\s*'
            r'<small data-i18n="supportedFormats">(.*?)</small>',
            markup,
        ).group(1)
        self.assertEqual(
            claim,
            "Supports JPG, PNG, WEBP, static AVIF, BMP, single-page TIFF, ICO, and TGA",
        )
        for unsupported_claim in ("GIF", "APNG", "animated AVIF", "multi-page TIFF", "PSD", "DDS", "JPEG 2000"):
            self.assertNotIn(unsupported_claim, claim)
        self.assertIn('id="edgeOptimize"', markup)
        self.assertIn('id="transparentBackground"', markup)
        self.assertIn('id="backgroundColor"', markup)
        self.assertIn('form.append("outputFormat"', script)
        self.assertIn('form.append("backgroundColor"', script)
        self.assertIn("function resetSettings", script)
        self.assertIn("function outputSupportsTransparency", script)
        self.assertNotIn("selectAllBtn", script)
        self.assertNotIn("显存", markup)
        self.assertNotIn("版本", markup)

    def test_frontend_picker_and_queue_accept_extended_input_formats(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('accept="image/*,.psd,.qoi,.jp2', markup)
        self.assertIn("supportedImageExtensionPattern", script)
        self.assertIn("psd|qoi", script)

    def test_frontend_selects_models_and_provider_through_one_runtime_request(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn('id="modelSelect"', markup)
        self.assertIn('id="providerSelect"', markup)
        self.assertIn('id="modelHelp"', markup)
        self.assertIn('id="runtimeToast"', markup)
        self.assertIn('for="modelSelect"', markup)
        self.assertIn('fetch("/api/models")', script)
        self.assertIn('fetch("/api/providers")', script)
        self.assertIn('fetch("/api/runtime/select"', script)
        self.assertNotIn('localStorage.getItem("koutu-model")', script)
        self.assertIn("async function loadRuntimeControls", script)
        self.assertIn("async function selectRuntime", script)
        self.assertIn(".model-select", css)

    def test_frontend_exposes_line_art_mode_and_submits_it(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('name="processingMode"', markup)
        self.assertIn('value="line_art"', markup)
        self.assertIn("不使用模型，适合背景单一的线稿或签名图", script)
        self.assertIn('form.append("processingMode"', script)
        self.assertIn("selectedProcessingMode", script)

    def test_processing_mode_uses_a_compact_topbar_segmented_control(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('class="top-runtime-control top-processing-control"', markup)
        self.assertNotIn('class="mode-info"', markup)
        self.assertIn('class="segmented processing-mode-control"', markup)
        self.assertIn('id="processingModeHint" class="top-mode-hint" hidden', markup)
        self.assertIn(".processing-mode-control", css)
        self.assertIn(".segmented input:focus-visible + span", css)
        self.assertIn("els.processingModeHint.hidden = !lineArtMode", script)
        self.assertIn("不使用模型，适合背景单一的线稿或签名图", script)

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

        self.assertIn('data-i18n="openCurrentResults"', markup)
        self.assertIn("currentRunId", script)
        self.assertIn("function openCurrentRunFolder", script)
        self.assertIn('fetch("/api/open-output"', script)
        self.assertIn("function loadRecentTask", script)
        self.assertIn("/api/tasks/recent?limit=1", script)
        self.assertIn("inputUrl", script)

    def test_frontend_uses_concise_service_status_and_post_side_effects(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn("本地部署", markup)
        self.assertIn("RMBG-2.0 ONNX", markup)
        self.assertNotIn("providerBadge", markup)
        self.assertNotIn("无需云端", markup)
        self.assertIn('id="statusText"', markup)
        self.assertIn('服务已就绪', script)
        self.assertNotIn(">GPU/CUDA<", markup)
        self.assertIn('method: "POST"', script)
        self.assertIn('headers: { "Content-Type": "application/json" }', script)
        self.assertIn("JSON.stringify({ path: item.outputPath })", script)
        self.assertIn("JSON.stringify({ runId: state.currentRunId })", script)
        self.assertIn("本地服务访问令牌已失效", script)

    def test_frontend_renders_structured_failure_details(self):
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn("function formatFailureDetail", script)
        self.assertIn("失败阶段", script)
        self.assertIn("错误原因", script)
        self.assertIn("处理建议", script)
        self.assertIn("错误码", script)
        self.assertIn("failure-detail", script)
        self.assertIn(".failure-detail", css)

    def test_frontend_previews_and_confirms_history_cleanup(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="historySummary"', markup)
        self.assertIn('id="historyFeedback"', markup)
        self.assertIn('aria-live="polite"', markup)
        self.assertIn('id="cleanupHistoryBtn"', markup)
        self.assertIn('data-i18n="quickCleanup">Quick cleanup', markup)
        self.assertIn("/api/tasks/history?protectRunId=", script)
        self.assertIn("fetch(historySummaryUrl())", script)
        self.assertIn('fetch("/api/tasks/cleanup"', script)
        self.assertIn("cleanupBytes", script)
        self.assertIn('t("taskSummary", { count: data.totalTasks || 0, size: formatBytes(data.totalBytes) })', script)
        self.assertNotIn("保留规则", script)
        self.assertIn("window.confirm", script)
        self.assertIn("function setHistoryFeedback", script)
        self.assertIn("function quickCleanupHistory", script)
        self.assertIn('t("noCleanupTasks", { days })', script)

    def test_right_sidebar_manages_history_tasks_and_quick_cleanup(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn('id="taskManagerTitle" data-i18n="taskManager">Task manager', markup)
        self.assertIn('id="historyTaskList"', markup)
        self.assertIn('id="selectAllHistory"', markup)
        self.assertIn('id="deleteSelectedTasksBtn"', markup)
        self.assertIn('data-cleanup-days="7"', markup)
        self.assertIn('data-cleanup-days="30"', markup)
        self.assertIn('fetch(`/api/tasks/${encodeURIComponent(runId)}`', script)
        self.assertIn('fetch("/api/tasks/delete"', script)
        self.assertIn("function renderHistoryTasks", script)
        self.assertIn("function viewHistoryTask", script)
        self.assertIn("function deleteSelectedTasks", script)
        self.assertIn("function quickCleanupHistory", script)
        self.assertIn(".history-task-list", css)
        self.assertIn(".history-task-card", css)

    def test_frontend_helper_text_is_concise_and_contextual(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn("The service remembers the last model it loaded successfully", markup)
        self.assertIn("Includes images in subfolders", markup)
        self.assertIn("Slightly softens transparent edges to reduce jaggedness", markup)
        self.assertIn('data-i18n="selectAll">Select all</span>', markup)
        self.assertNotIn("批量选择多个文件", markup)
        self.assertNotIn("查看本次处理进度与结果", markup)
        self.assertNotIn("查看、复选或删除已完成任务", markup)
        self.assertNotIn("当前已选择 0 张图片", markup)
        self.assertNotIn('"当前已选择 0 张图片"', script)
        self.assertIn(".privacy-note:empty", css)

    def test_frontend_adds_state_driven_motion_feedback(self):
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("--motion-fast", css)
        self.assertIn("@keyframes panel-enter", css)
        self.assertIn("@keyframes preview-reveal", css)
        self.assertIn("function revealPreview", script)
        self.assertIn('document.body.classList.add("is-processing")', script)
        self.assertIn('document.body.classList.remove("is-processing")', script)

    def test_frontend_motion_respects_user_preferences_and_announces_updates(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("animation-duration: 0.01ms !important", css)
        self.assertIn('id="statusText" class="status" aria-live="polite"', markup)
        self.assertIn('id="quotaText" class="privacy-note" aria-live="polite"', markup)

    def test_frontend_supports_persistent_light_and_dark_themes(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="themeToggleBtn"', markup)
        self.assertIn('id="themeLabel"', markup)
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn("function applyTheme", script)
        self.assertIn('localStorage.getItem("koutu-theme")', script)
        self.assertIn('localStorage.setItem("koutu-theme"', script)
        self.assertIn("prefers-color-scheme: dark", script)

    def test_frontend_buttons_share_hover_and_press_feedback(self):
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn(".theme-toggle:not(:disabled):hover", css)
        self.assertIn(".download:not(.disabled):hover", css)
        self.assertIn(".ghost:not(:disabled):hover", css)
        self.assertIn(".card-open:not(:disabled):hover", css)
        self.assertIn(".theme-toggle:active", css)
        self.assertIn(".theme-toggle:focus-visible", css)

    def test_theme_controls_stay_compact_on_small_screens(self):
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn("@media (max-width: 520px)", css)
        self.assertIn("#themeLabel", css)
        self.assertIn("#openOutputBtn", css)

    def test_workspace_uses_compact_three_columns_before_stacking_task_management(self):
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        compact_desktop = re.search(r"@media \(max-width: 1280px\) \{(.*?)\n\}", css, re.S)
        medium_layout = re.search(r"@media \(max-width: 1120px\) \{(.*?)\n\}", css, re.S)

        self.assertIsNotNone(compact_desktop)
        self.assertIn("grid-template-columns: minmax(264px, 0.72fr) minmax(480px, 1.35fr) minmax(300px, 0.82fr)", compact_desktop.group(1))
        self.assertNotIn("grid-column: 1 / -1", compact_desktop.group(1))
        self.assertIsNotNone(medium_layout)
        self.assertIn("grid-column: 1 / -1", medium_layout.group(1))

    def test_desktop_panels_align_in_height_and_action_buttons_use_size_tiers(self):
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        desktop_layout = re.search(r"@media \(min-width: 1121px\) \{(.*?)\n\}", css, re.S)

        self.assertIsNotNone(desktop_layout)
        self.assertIn("height: calc(100dvh - 120px);", desktop_layout.group(1))
        self.assertIn("overflow: auto;", desktop_layout.group(1))
        self.assertRegex(css, r"\.section-head \.ghost,\n\.section-head \.download\s*\{[^}]*min-height:\s*36px;")
        self.assertRegex(css, r"\.task-actions \.ghost\s*\{[^}]*min-height:\s*44px;")
        self.assertRegex(
            css,
            r"\.history-management \.tiny,\n\.history-task-actions button,\n\.card-open\s*\{[^}]*min-height:\s*30px;",
        )

    def test_preview_actions_use_compact_line_icons(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        preview_actions = markup[markup.index('<div class="preview-actions">') : markup.index("</div>", markup.index('<div class="preview-actions">'))]

        self.assertIn('class="button-icon"', preview_actions)
        self.assertIn('id="rerunBtn"', preview_actions)
        self.assertIn('id="downloadFirstBtn"', preview_actions)
        self.assertIn(".button-icon", css)

    def test_runtime_controls_and_panels_keep_compact_fixed_layouts(self):
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertRegex(
            css,
            r"\.top-runtime-control:first-child\s*\{[^}]*width:\s*190px;[^}]*\}\s*"
            r"\.top-runtime-control:nth-child\(2\)\s*\{[^}]*width:\s*190px;",
        )
        self.assertRegex(
            css,
            r"\.history-task-list\s*\{[^}]*height:\s*260px;[^}]*overflow-y:\s*auto;[^}]*overscroll-behavior:\s*contain;",
        )

    def test_runtime_feedback_dismisses_after_three_seconds_and_buttons_have_tactile_motion(self):
        script = (RUNNER_DIR / "web" / "app.js").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn("let runtimeToastTimer", script)
        self.assertIn("window.setTimeout", script)
        self.assertIn("}, 3000);", script)
        self.assertIn('els.runtimeToast.hidden = true', script)
        self.assertIn("button:not(:disabled):hover", css)

    def test_side_and_task_panels_use_fixed_proportional_sections(self):
        markup = (RUNNER_DIR / "web" / "index.html").read_text(encoding="utf-8")
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")

        self.assertIn('class="task-content"', markup)
        self.assertIn('class="current-task-section"', markup)
        self.assertIn('<h2 id="taskManagerTitle" data-i18n="taskManager">Task manager</h2>', markup)
        self.assertIn('<h2 data-i18n="historyTasks">Task history</h2>', markup)
        self.assertRegex(
            css,
            r"\.side-panel\s*\{[^}]*grid-template-rows:\s*minmax\(0, 2fr\) minmax\(0, 2fr\) minmax\(0, 1fr\);",
        )
        self.assertRegex(css, r"\.task-content\s*\{[^}]*grid-template-rows:\s*minmax\(0, 1fr\) minmax\(0, 1fr\);")
        self.assertRegex(css, r"\.current-task-section,\n\.history-management\s*\{[^}]*min-height:\s*0;")
        self.assertRegex(css, r"\.result-grid,\n\.history-task-list\s*\{[^}]*flex:\s*1 1 auto;")

    def test_primary_button_palette_keeps_white_text_accessible_in_both_themes(self):
        css = (RUNNER_DIR / "web" / "style.css").read_text(encoding="utf-8")
        light = re.search(r":root\s*\{(.*?)\n\}", css, re.S).group(1)
        dark = re.search(r'\[data-theme="dark"\]\s*\{(.*?)\n\}', css, re.S).group(1)

        for theme in (light, dark):
            for token in ("accent", "accent-highlight"):
                color = re.search(rf"--{token}:\s*(#[0-9a-fA-F]{{6}})", theme).group(1)
                self.assertGreaterEqual(contrast_ratio("#ffffff", color), 4.5)

if __name__ == "__main__":
    unittest.main()
