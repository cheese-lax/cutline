const state = {
  files: [],
  results: [],
  processing: false,
  selectedIndex: -1,
  selectedObjectUrl: "",
  currentRunId: "",
  currentOutputDir: "",
  activeModel: "",
  historyTasks: [],
  selectedHistoryRunIds: new Set(),
  progress: {
    total: 0,
    processed: 0,
    success: 0,
    failed: 0,
  },
};

const els = {
  statusText: document.querySelector("#statusText"),
  modelSelect: document.querySelector("#modelSelect"),
  providerSelect: document.querySelector("#providerSelect"),
  modelHelp: document.querySelector("#modelHelp"),
  modelsDirectory: document.querySelector("#modelsDirectory"),
  runtimeToast: document.querySelector("#runtimeToast"),
  themeToggleBtn: document.querySelector("#themeToggleBtn"),
  themeLabel: document.querySelector("#themeLabel"),
  openOutputBtn: document.querySelector("#openOutputBtn"),
  openOutputBtnBottom: document.querySelector("#openOutputBtnBottom"),
  dropZone: document.querySelector("#dropZone"),
  originalUploadZone: document.querySelector("#originalUploadZone"),
  chooseSingleBtn: document.querySelector("#chooseSingleBtn"),
  chooseFilesBtn: document.querySelector("#chooseFilesBtn"),
  chooseFolderBtn: document.querySelector("#chooseFolderBtn"),
  singleFileInput: document.querySelector("#singleFileInput"),
  fileInput: document.querySelector("#fileInput"),
  folderInput: document.querySelector("#folderInput"),
  clearBtn: document.querySelector("#clearBtn"),
  processBtn: document.querySelector("#processBtn"),
  rerunBtn: document.querySelector("#rerunBtn"),
  quotaText: document.querySelector("#quotaText"),
  originalPreview: document.querySelector("#originalPreview"),
  resultPreview: document.querySelector("#resultPreview"),
  downloadFirstBtn: document.querySelector("#downloadFirstBtn"),
  resultTitle: document.querySelector("#resultTitle"),
  resultGrid: document.querySelector("#resultGrid"),
  progressBar: document.querySelector("#progressBar span"),
  clearListBtn: document.querySelector("#clearListBtn"),
  historySummary: document.querySelector("#historySummary"),
  historyFeedback: document.querySelector("#historyFeedback"),
  historyTaskList: document.querySelector("#historyTaskList"),
  refreshHistoryBtn: document.querySelector("#refreshHistoryBtn"),
  selectAllHistory: document.querySelector("#selectAllHistory"),
  deleteSelectedTasksBtn: document.querySelector("#deleteSelectedTasksBtn"),
  cleanupHistoryBtn: document.querySelector("#cleanupHistoryBtn"),
  totalCount: document.querySelector("#totalCount"),
  processingCount: document.querySelector("#processingCount"),
  completedCount: document.querySelector("#completedCount"),
  pendingCount: document.querySelector("#pendingCount"),
  edgeOptimize: document.querySelector("#edgeOptimize"),
  edgeOptimizeHint: document.querySelector("#edgeOptimizeHint"),
  transparentBackground: document.querySelector("#transparentBackground"),
  backgroundColor: document.querySelector("#backgroundColor"),
  backgroundColorText: document.querySelector("#backgroundColorText"),
  backgroundHint: document.querySelector("#backgroundHint"),
  processingModeHint: document.querySelector("#processingModeHint"),
  fileNameMeta: document.querySelector("#fileNameMeta"),
  resolutionMeta: document.querySelector("#resolutionMeta"),
  formatMeta: document.querySelector("#formatMeta"),
};

const preferredThemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
let runtimeToastTimer;
const translations = {
  en: {
    pageTitle: "Cutline Local Background Removal", languageSelector: "Language selector", processingSettings: "Processing settings",
    backgroundRemovalModel: "Background removal model", modelMemoryHint: "The service remembers the last model it loaded successfully", loadingModels: "Reading the models folder…", inferenceProvider: "Inference provider", processingMode: "Processing mode", smartRemoval: "Smart removal", lineArtMode: "Line art", addModelPrefix: "Place an ONNX model in ", addModelSuffix: ", then refresh this page.", downloadModel: "Download the RMBG-2.0 ONNX model", modelLicenseNotice: "Confirm the model license before downloading or using it.", checkingService: "Checking service", upload: "Upload", uploadSingle: "Upload one image", uploadMultiple: "Upload multiple images", chooseFolder: "Choose folder", supportedFormats: "Supports JPG, PNG, WEBP, static AVIF, BMP, single-page TIFF, ICO, and TGA", includeSubfolders: "Includes images in subfolders", dropZone: "You can also drag images or folders here", outputSettings: "Output settings", reset: "Reset", outputFormat: "Output format", edgeOptimization: "Edge optimization", edgeOptimizeHint: "Slightly softens transparent edges to reduce jaggedness", transparentBackground: "Transparent background", backgroundColor: "Background color", backgroundHint: "Only applies when transparent background is off", startRemoval: "Start removal", preview: "Preview", rerunRemoval: "Run again", download: "Download", original: "Original", originalUploadArea: "Original image upload area. Drag or paste an image.", dragOrPaste: "Drag or paste an image here", result: "Result", waitingForProcessing: "Waiting to process", fileName: "File name", resolution: "Resolution", taskManager: "Task manager", clearList: "Clear list", currentTask: "Current task", total: "Total", processing: "Processing", completed: "Completed", pending: "Pending", openCurrentResults: "Open current results folder", historyTasks: "Task history", refresh: "Refresh", calculatingStorage: "Calculating storage…", selectAll: "Select all", deleteSelected: "Delete selected", quickCleanup: "Quick cleanup", cleanOlderThan7: "Clean older than 7 days", cleanOlderThan30: "Clean older than 30 days", darkMode: "Dark mode", lightMode: "Light mode", switchToDark: "Switch to dark theme", switchToLight: "Switch to light theme", noModel: "No available model", loading: "Loading model…", ready: "Service ready", processingImages: "Processing images…", switching: "Switching model…", runtimeError: "Model runtime error", stopped: "Model service stopped", serviceUnavailable: "Service unavailable", selectedImages: "{count} image(s) selected", openResultsTitle: "Open results folder for {runId}", openResultsHint: "Process images to open this run's results folder", transparent: "transparent background", lineArtTransparent: "line art, transparent background", background: "{color} background", lineArtHint: "No model is used; ideal for simple line art or signatures.", lineArtJpgHint: "No model is used; ideal for simple line art or signatures. JPG is composited with the selected background color.", jpgHint: "JPG does not support transparency; it will be composited with the selected background color", lineArtAlwaysTransparent: "Line art mode always uses a transparent background", backgroundColorHint: "Composites transparent areas with the selected background color", clickOriginal: "Click to view the original", waiting: "Waiting", clickCompare: "Click to compare; double-click to open the image folder", failed: "Failed", clickFailure: "Click to view the original and error details", viewing: "Viewing", locate: "Locate", failureStage: "Failure stage: {value}", failureReason: "Failure reason: {value}", suggestion: "Suggestion: {value}", errorCode: "Error code: {value}", unknown: "Unknown", noErrorDetail: "No error detail provided", retryAndCheckLogs: "Retry; if the problem continues, check the server log.", completedBatch: "Completed {success}; failed {failed}. Results: {outputDir}{failure}", processingStart: "Starting {total} image(s)", removingProgress: "Removing background {processed}/{total}", removingStart: "Starting background removal…", finalizing: "Finalizing…", uploading: "Uploading…", submitting: "Submitting {count} image(s)", tokenExpired: "The local service access token expired. Restart the launch script.", uploadTooLarge: "Upload exceeds the service limit.", requestFailed: "Request failed (HTTP {status}): {error}{detail}{suggestion}", checkServerLogs: " Check the server log and retry.", unableOpenResults: "Unable to open the results folder", unableOpenCurrentResults: "Unable to open this run's results folder", modelLoading: "Loading model…", modelSwitchFailed: "Model switch failed", modelSwitchSuccess: "Model switched: {model} · {provider} · {seconds} seconds", switchAfterProcessing: "A task is processing. Finish it before switching the model or provider.", noModelInFolder: "No ONNX model found in the models folder", unableReadModels: "Unable to read model list", running: "Running", completedWithFailed: "Completed, {count} failed", deleteSelectedCount: "Delete selected ({count})", noHistory: "No task history", selectTask: "Select task {runId}", currentViewing: " · currently viewing", view: "View", delete: "Delete", deleteTask: "Delete this history task", cannotDeleteTask: "Current or running tasks cannot be deleted", taskSummary: "{count} task(s) · {size}", unableHistorySummary: "Unable to read task history", loadHistoryFailed: "Failed to load task history: {error}", loadingTask: "Loading task details…", taskLoadFailed: "Failed to load task details", selectedHistoryTask: "Selected history task", loadedTask: "Loaded task {runId}.", viewFailed: "View failed: {error}", deleteConfirm: "Permanently delete {count} task(s)?", deletionCancelled: "Deletion cancelled.", deletingTasks: "Deleting {count} task(s)…", deleteHistoryFailed: "Failed to delete task history", deletedTasks: "Deleted {count} task(s), freed {size}.", deleteFailed: "Delete failed: {error}", checkingOldTasks: "Checking tasks older than {days} days…", cleanupPreviewFailed: "Unable to preview cleanup", noCleanupTasks: "No cleanup-eligible tasks older than {days} days.", cleanupConfirm: "Delete {count} task(s) older than {days} days and free about {size}?", cleanupCancelled: "Quick cleanup cancelled.", cleaningTasks: "Cleaning tasks older than {days} days…", quickCleanupFailed: "Quick cleanup failed", cleanedTasks: "Cleaned {count} task(s), freed {size}.", cleanupFailed: "Cleanup failed: {error}", restoredTask: "Restored recent task: {runId}", currentTaskStatus: "Current task",
  },
  "zh-CN": {
    pageTitle: "Cutline 本地抠图", languageSelector: "语言选择", processingSettings: "处理设置", backgroundRemovalModel: "抠图模型", modelMemoryHint: "服务会记住上次成功加载的模型", loadingModels: "正在读取 models 文件夹…", inferenceProvider: "推理方式", processingMode: "处理模式", smartRemoval: "智能抠图", lineArtMode: "线稿模式", addModelPrefix: "将 ONNX 模型放入 ", addModelSuffix: " 后刷新页面。", downloadModel: "下载 RMBG-2.0 ONNX 模型", modelLicenseNotice: "下载和使用前请确认模型许可证。", checkingService: "服务检查中", upload: "上传", uploadSingle: "上传单张图片", uploadMultiple: "上传多张图片", chooseFolder: "选择文件夹", supportedFormats: "支持 JPG、PNG、WEBP、静态 AVIF、BMP、单页 TIFF、ICO、TGA", includeSubfolders: "包含子文件夹中的图片", dropZone: "也可以把图片或文件夹拖到这里", outputSettings: "输出设置", reset: "重置", outputFormat: "输出格式", edgeOptimization: "边缘优化", edgeOptimizeHint: "轻微柔化透明边缘，减少锯齿", transparentBackground: "透明背景", backgroundColor: "背景颜色", backgroundHint: "仅在关闭透明背景时生效", startRemoval: "开始抠图", preview: "预览", rerunRemoval: "重新抠图", download: "下载", original: "原图", originalUploadArea: "原图上传区域，支持拖拽或粘贴图片", dragOrPaste: "拖拽或粘贴图片到这里", result: "抠图结果", waitingForProcessing: "等待处理", fileName: "文件名", resolution: "分辨率", taskManager: "任务管理", clearList: "清空列表", currentTask: "当前任务", total: "总数", processing: "处理中", completed: "已完成", pending: "待处理", openCurrentResults: "打开本次结果文件夹", historyTasks: "历史任务", refresh: "刷新", calculatingStorage: "正在计算占用空间…", selectAll: "全选", deleteSelected: "删除所选", quickCleanup: "一键清理", cleanOlderThan7: "清理 7 天前", cleanOlderThan30: "清理 30 天前", darkMode: "深色模式", lightMode: "浅色模式", switchToDark: "切换到深色主题", switchToLight: "切换到浅色主题", noModel: "未找到可用模型", loading: "正在加载模型…", ready: "服务已就绪", processingImages: "正在处理图片…", switching: "正在切换模型…", runtimeError: "模型运行环境异常", stopped: "模型服务已停止", serviceUnavailable: "服务未就绪", selectedImages: "当前已选择 {count} 张图片", openResultsTitle: "打开 {runId} 的结果目录", openResultsHint: "完成一次抠图后可打开本次结果目录", transparent: "透明背景", lineArtTransparent: "线稿透明背景", background: "{color} 背景", lineArtHint: "不使用模型，适合背景单一的线稿或签名图", lineArtJpgHint: "不使用模型，适合背景单一的线稿或签名图；JPG 会按所选背景色合成。", jpgHint: "JPG 不支持透明通道，将自动合成为所选背景色", lineArtAlwaysTransparent: "线稿模式始终输出透明背景", backgroundColorHint: "将透明区域合成为所选背景色", clickOriginal: "单击查看原图", waiting: "等待中", clickCompare: "单击查看对比，双击打开图片所在文件夹", failed: "失败", clickFailure: "单击查看原图和失败信息", viewing: "查看中", locate: "定位", failureStage: "失败阶段：{value}", failureReason: "错误原因：{value}", suggestion: "处理建议：{value}", errorCode: "错误码：{value}", unknown: "未知", noErrorDetail: "未提供具体错误", retryAndCheckLogs: "请重试；若持续失败，请查看服务端日志。", completedBatch: "完成 {success} 张，失败 {failed} 张；结果目录：{outputDir}{failure}", processingStart: "开始处理 {total} 张图片", removingProgress: "正在抠图 {processed}/{total}", removingStart: "正在抠图...", finalizing: "正在收尾...", uploading: "正在上传...", submitting: "正在提交 {count} 张图片", tokenExpired: "本地服务访问令牌已失效，请重新运行启动脚本。", uploadTooLarge: "上传内容超过服务限制。", requestFailed: "请求失败（HTTP {status}）：{error}{detail}{suggestion}", checkServerLogs: " 请查看服务端日志后重试。", unableOpenResults: "无法打开结果文件夹", unableOpenCurrentResults: "无法打开本次结果文件夹", modelLoading: "模型加载中…", modelSwitchFailed: "模型切换失败", modelSwitchSuccess: "模型切换成功：{model} · {provider} · {seconds} 秒", switchAfterProcessing: "当前有任务正在处理，请完成后再切换模型或推理方式。", noModelInFolder: "models 文件夹中未找到 ONNX 模型", unableReadModels: "无法读取模型列表", running: "进行中", completedWithFailed: "完成，{count} 个失败", deleteSelectedCount: "删除所选 ({count})", noHistory: "暂无历史任务", selectTask: "选择任务 {runId}", currentViewing: " · 当前查看", view: "查看", delete: "删除", deleteTask: "删除这个历史任务", cannotDeleteTask: "当前或运行中任务不可删除", taskSummary: "{count} 个任务 · {size}", unableHistorySummary: "无法读取历史结果统计", loadHistoryFailed: "加载历史任务失败：{error}", loadingTask: "正在加载任务详情…", taskLoadFailed: "任务详情加载失败", selectedHistoryTask: "已选历史任务", loadedTask: "已加载任务 {runId}。", viewFailed: "查看失败：{error}", deleteConfirm: "将永久删除 {count} 个历史任务，是否继续？", deletionCancelled: "已取消删除。", deletingTasks: "正在删除 {count} 个任务…", deleteHistoryFailed: "删除历史任务失败", deletedTasks: "已删除 {count} 个任务，释放 {size}。", deleteFailed: "删除失败：{error}", checkingOldTasks: "正在检查 {days} 天前的历史任务…", cleanupPreviewFailed: "无法预览清理结果", noCleanupTasks: "没有 {days} 天前的可清理任务。", cleanupConfirm: "将删除 {count} 个 {days} 天前的任务，预计释放 {size}。是否继续？", cleanupCancelled: "已取消一键清理。", cleaningTasks: "正在清理 {days} 天前的任务…", quickCleanupFailed: "一键清理失败", cleanedTasks: "已清理 {count} 个任务，释放 {size}。", cleanupFailed: "清理失败：{error}", restoredTask: "已恢复最近任务：{runId}", currentTaskStatus: "当前任务",
  },
};
let activeLanguage = "en";

function t(key, values = {}) {
  return (translations[activeLanguage][key] || translations.en[key] || key).replace(
    /\\{(\\w+)\\}/g,
    (_, name) => values[name] ?? `{${name}}`,
  );
}

function storedLanguage() {
  try {
    return localStorage.getItem("cutline-language") === "zh-CN" ? "zh-CN" : "en";
  } catch (error) {
    return "en";
  }
}

function initialLanguage() {
  return storedLanguage();
}

function applyLanguage(language, persist = false) {
  activeLanguage = language === "zh-CN" ? "zh-CN" : "en";
  document.documentElement.lang = activeLanguage;
  document.title = t("pageTitle");
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((element) => {
    element.title = t(element.dataset.i18nTitle);
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });
  document.querySelectorAll("[data-language]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.language === activeLanguage));
  });
  applyTheme(document.documentElement.dataset.theme || initialTheme());
  updateFormatMeta();
  renderSelection();
  renderQueue();
  if (persist) {
    try {
      localStorage.setItem("cutline-language", activeLanguage);
    } catch (error) {
      // Keep the chosen language for the current session if storage is unavailable.
    }
  }
}

const supportedImageExtensionPattern =
  /\.(apng|avifs?|bmp|dds|dib|gif|icb|ico|j2[ck]|jfif|jp[2cefx]|jpe?g|p[bgfnp]m|png|psd|qoi|tga|tiff?|vda|vst|webp)$/i;
const runtimeStateText = {
  no_model: "noModel",
  loading: "loading",
  ready: "ready",
  processing: "processingImages",
  switching: "switching",
  error: "runtimeError",
  stopped: "stopped",
};

function storedTheme() {
  try {
    const theme = localStorage.getItem("koutu-theme");
    return theme === "dark" || theme === "light" ? theme : "";
  } catch (error) {
    return "";
  }
}

function applyTheme(theme, persist = false) {
  const normalized = theme === "dark" ? "dark" : "light";
  const dark = normalized === "dark";
  document.documentElement.dataset.theme = normalized;
  els.themeToggleBtn.setAttribute("aria-pressed", String(dark));
  els.themeToggleBtn.setAttribute("aria-label", t(dark ? "switchToLight" : "switchToDark"));
  els.themeToggleBtn.title = t(dark ? "switchToLight" : "switchToDark");
  els.themeLabel.textContent = t(dark ? "lightMode" : "darkMode");
  if (persist) {
    try {
      localStorage.setItem("koutu-theme", normalized);
    } catch (error) {
      // 浏览器禁用本地存储时仍保留当前会话主题。
    }
  }
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme;
  applyTheme(current === "dark" ? "light" : "dark", true);
}

function initialTheme() {
  return storedTheme() || (preferredThemeQuery.matches ? "dark" : "light");
}

function supported(file) {
  return /^image\//.test(file.type) || supportedImageExtensionPattern.test(file.name);
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
}

function makeEntry(file, path) {
  return {
    file,
    path: path || file.webkitRelativePath || file.name,
  };
}

function relativeName(entry) {
  return entry.path || entry.file.name;
}

function selectedOutputFormat() {
  return document.querySelector('input[name="outputFormat"]:checked')?.value || "png";
}

function outputSupportsTransparency(outputFormat) {
  return outputFormat !== "jpg";
}

function selectedProcessingMode() {
  return document.querySelector('input[name="processingMode"]:checked')?.value || "rmbg";
}

function normalizeHex(value) {
  const raw = (value || "").trim();
  if (/^#[0-9a-f]{6}$/i.test(raw)) {
    return raw.toUpperCase();
  }
  return "#FFFFFF";
}

function currentSettings() {
  const processingMode = selectedProcessingMode();
  const outputFormat = selectedOutputFormat();
  const supportsTransparency = outputSupportsTransparency(outputFormat);
  return {
    processingMode,
    outputFormat,
    edgeOptimize: els.edgeOptimize.checked,
    transparentBackground:
      supportsTransparency && (processingMode === "line_art" || els.transparentBackground.checked),
    backgroundColor: normalizeHex(els.backgroundColorText.value || els.backgroundColor.value),
  };
}

function setFiles(files) {
  setEntries(Array.from(files).map((file) => makeEntry(file)));
}

function clipboardImageFiles(clipboardData) {
  const itemFiles = Array.from(clipboardData?.items || [])
    .filter((item) => item.kind === "file" && /^image\//.test(item.type))
    .map((item) => item.getAsFile())
    .filter(Boolean);
  const files = itemFiles.length > 0 ? itemFiles : Array.from(clipboardData?.files || []);
  return files.filter(supported);
}

function handleImagePaste(event) {
  const files = clipboardImageFiles(event.clipboardData);
  if (files.length === 0) return;
  event.preventDefault();
  setFiles(files);
}

function setEntries(entries) {
  const seen = new Set();
  state.files = entries
    .filter((entry) => supported(entry.file))
    .filter((entry) => {
      const key = `${relativeName(entry)}:${entry.file.size}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  state.results = [];
  state.selectedIndex = state.files.length > 0 ? 0 : -1;
  state.currentRunId = "";
  state.currentOutputDir = "";
  state.progress = { total: state.files.length, processed: 0, success: 0, failed: 0 };
  updateFormatMeta();
  els.quotaText.textContent = state.files.length ? t("selectedImages", { count: state.files.length }) : "";
  setProgress(0);
  renderSelection();
  renderQueue();
}

function renderSelection() {
  const hasFiles = state.files.length > 0;
  els.processBtn.disabled = !hasFiles || state.processing;
  els.rerunBtn.disabled = !hasFiles || state.processing;
  els.modelSelect.disabled =
    state.processing ||
    els.modelSelect.dataset.switching === "true" ||
    els.modelSelect.options.length === 0;
  els.providerSelect.disabled = els.modelSelect.disabled;
  updateTaskActions();
}

function updateTaskActions() {
  const hasRun = Boolean(state.currentRunId);
  els.openOutputBtn.disabled = !hasRun;
  els.openOutputBtnBottom.disabled = !hasRun;
  const title = hasRun ? t("openResultsTitle", { runId: state.currentRunId }) : t("openResultsHint");
  els.openOutputBtn.title = title;
  els.openOutputBtnBottom.title = title;
}

function queueLength() {
  return Math.max(state.files.length, state.results.length);
}

function clampSelectedIndex() {
  const total = queueLength();
  if (total === 0) {
    state.selectedIndex = -1;
    return;
  }
  if (state.selectedIndex < 0 || state.selectedIndex >= total) {
    state.selectedIndex = 0;
  }
}

function withQueueIndex(item, index) {
  return {
    ...item,
    queueIndex: Number.isInteger(item.queueIndex) ? item.queueIndex : index,
  };
}

function updateOriginalPreview() {
  if (state.selectedObjectUrl) {
    URL.revokeObjectURL(state.selectedObjectUrl);
    state.selectedObjectUrl = "";
  }

  const entry = state.files[state.selectedIndex];
  if (!entry) {
    els.originalPreview.removeAttribute("src");
    els.originalPreview.removeAttribute("alt");
    els.originalPreview.classList.remove("is-revealed");
    els.fileNameMeta.textContent = "-";
    els.resolutionMeta.textContent = "-";
    return;
  }

  const sourceUrl = entry.file ? URL.createObjectURL(entry.file) : entry.inputUrl;
  if (!sourceUrl) {
    els.originalPreview.removeAttribute("src");
    els.originalPreview.removeAttribute("alt");
    els.fileNameMeta.textContent = relativeName(entry);
    els.resolutionMeta.textContent = "-";
    return;
  }
  if (entry.file) {
    state.selectedObjectUrl = sourceUrl;
  }
  els.resolutionMeta.textContent = "-";
  els.originalPreview.onload = () => {
    els.resolutionMeta.textContent = `${els.originalPreview.naturalWidth} x ${els.originalPreview.naturalHeight}`;
    revealPreview(els.originalPreview);
  };
  els.originalPreview.src = sourceUrl;
  els.originalPreview.alt = relativeName(entry);
  els.fileNameMeta.textContent = relativeName(entry);
}

function updateFormatMeta() {
  const settings = currentSettings();
  const lineArtMode = settings.processingMode === "line_art";
  const supportsTransparency = outputSupportsTransparency(settings.outputFormat);
  const background = settings.transparentBackground ? t("transparent") : t("background", { color: settings.backgroundColor });
  els.formatMeta.textContent = `${settings.outputFormat.toUpperCase()}（${
    lineArtMode && settings.transparentBackground ? t("lineArtTransparent") : background
  }）`;
  els.edgeOptimize.disabled = lineArtMode;
  els.edgeOptimizeHint.hidden = lineArtMode;
  els.transparentBackground.disabled = lineArtMode || !supportsTransparency;
  const backgroundDisabled = supportsTransparency && (lineArtMode || settings.transparentBackground);
  els.backgroundColor.disabled = backgroundDisabled;
  els.backgroundColorText.disabled = backgroundDisabled;
  els.processingModeHint.hidden = !lineArtMode;
  els.processingModeHint.textContent = !lineArtMode
    ? ""
    : supportsTransparency
    ? t("lineArtHint")
    : t("lineArtJpgHint");
  els.backgroundHint.textContent = !supportsTransparency
    ? t("jpgHint")
    : lineArtMode
    ? t("lineArtAlwaysTransparent")
    : settings.transparentBackground
    ? t("backgroundHint")
    : t("backgroundColorHint");
}

function updateStats() {
  const total = state.progress.total || state.files.length;
  const processed = state.progress.processed || state.results.length;
  const processing = state.processing && processed < total ? 1 : 0;
  const pending = Math.max(total - processed - processing, 0);

  els.totalCount.textContent = String(total);
  els.processingCount.textContent = String(processing);
  els.completedCount.textContent = String(processed);
  els.pendingCount.textContent = String(pending);
}

function renderQueue() {
  clampSelectedIndex();
  els.resultGrid.innerHTML = "";
  const total = queueLength();
  for (let index = 0; index < total; index += 1) {
    const result = state.results[index];
    if (result) {
      els.resultGrid.appendChild(createResultCard(result, index));
      continue;
    }
    const entry = state.files[index];
    if (entry) {
      const status = state.processing && index === state.results.length ? "processing" : "pending";
      els.resultGrid.appendChild(createPendingCard(entry, status, index));
    }
  }

  syncSelectedPreview();
  updateStats();
}

function prepareSelectableCard(card, index) {
  const isSelected = index === state.selectedIndex;
  card.setAttribute("data-index", String(index));
  card.setAttribute("role", "button");
  card.setAttribute("tabindex", "0");
  card.setAttribute("aria-selected", String(isSelected));
  card.classList.toggle("is-selected", isSelected);
  card.addEventListener("click", () => selectResult(index));
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectResult(index);
    }
  });
}

function createPendingCard(entry, status, index) {
  const card = document.createElement("article");
  card.className = `result-card ${status}`;
  prepareSelectableCard(card, index);
  card.title = t("clickOriginal");
  card.innerHTML = `
    <div class="queue-thumb placeholder"></div>
    <div class="result-meta">
      <strong title="${relativeName(entry)}">${entry.file.name}</strong>
      <span>${status === "processing" ? t("processing") : t("waiting")}</span>
    </div>
    <div class="card-state">${status === "processing" ? t("processing") : t("pending")}</div>
  `;
  return card;
}

function createResultCard(item, index) {
  const card = document.createElement("article");
  card.className = `result-card ${item.ok ? "done" : "failed"}`;
  prepareSelectableCard(card, index);

  const thumb = document.createElement("div");
  thumb.className = "queue-thumb";
  if (item.ok) {
    const img = document.createElement("img");
    img.src = item.outputUrl;
    img.alt = item.outputName || item.inputName;
    thumb.appendChild(img);
    card.title = t("clickCompare");
    card.addEventListener("dblclick", () => openResultFolder(item));
  } else {
    thumb.textContent = t("failed");
    card.title = t("clickFailure");
  }
  card.appendChild(thumb);

  const meta = document.createElement("div");
  meta.className = "result-meta";
  const title = document.createElement("strong");
  title.title = item.inputName;
  title.textContent = item.outputName || item.inputName;
  const detail = document.createElement("span");
  detail.title = item.outputPath || item.message;
  detail.textContent = item.ok ? item.outputPath : item.message;
  meta.append(title, detail);
  card.appendChild(meta);

  const status = document.createElement("div");
  status.className = "card-state";
  status.textContent = index === state.selectedIndex && item.ok ? t("viewing") : item.ok ? t("completed") : t("failed");
  card.appendChild(status);

  const openButton = document.createElement("button");
  openButton.className = "card-open";
  openButton.type = "button";
  openButton.textContent = item.ok ? t("locate") : "-";
  openButton.disabled = !item.ok;
  openButton.addEventListener("click", (event) => {
    event.stopPropagation();
    openResultFolder(item);
  });
  card.appendChild(openButton);

  if (!item.ok) {
    const failureDetail = document.createElement("div");
    failureDetail.className = "failure-detail";
    failureDetail.textContent = formatFailureDetail(item);
    card.appendChild(failureDetail);
  }
  return card;
}

function formatFailureDetail(item) {
  const error = item.error || {};
  return [
    t("failureStage", { value: error.stage || t("unknown") }),
    t("failureReason", { value: error.detail || error.reason || item.message || t("noErrorDetail") }),
    t("suggestion", { value: error.suggestion || t("retryAndCheckLogs") }),
    t("errorCode", { value: error.code || "PROCESS_FAILED" }),
  ].join("\n");
}

function completedBatchMessage(success, failed, outputDir) {
  const firstFailure = state.results.find((item) => item && !item.ok);
  const failure = firstFailure ? `；${formatFailureDetail(firstFailure).replaceAll("\n", "；")}` : "";
  return t("completedBatch", { success, failed, outputDir, failure });
}

function selectResult(index) {
  if (index < 0 || index >= queueLength()) return;
  state.selectedIndex = index;
  renderQueue();
}

function appendResult(item, queueIndex = state.results.length) {
  state.results[queueIndex] = withQueueIndex(item, queueIndex);
  if (state.selectedIndex < 0) {
    state.selectedIndex = queueIndex;
  }
  renderQueue();
}

function showResultPreview(item) {
  els.resultPreview.onload = () => revealPreview(els.resultPreview);
  els.resultPreview.src = item.outputUrl;
  els.resultPreview.alt = item.outputName || item.inputName;
  els.downloadFirstBtn.href = item.outputUrl;
  els.downloadFirstBtn.download = item.outputName;
  els.downloadFirstBtn.classList.remove("disabled");
}

function clearResultPreview() {
  els.resultPreview.removeAttribute("src");
  els.resultPreview.removeAttribute("alt");
  els.resultPreview.classList.remove("is-revealed");
  els.downloadFirstBtn.href = "#";
  els.downloadFirstBtn.classList.add("disabled");
}

function revealPreview(image) {
  image.classList.remove("is-revealed");
  requestAnimationFrame(() => {
    requestAnimationFrame(() => image.classList.add("is-revealed"));
  });
}

function syncSelectedPreview() {
  updateOriginalPreview();
  const item = state.results[state.selectedIndex];
  if (item && item.ok) {
    showResultPreview(item);
    return;
  }
  clearResultPreview();
}

function setProgress(percent) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  els.progressBar.style.width = `${value}%`;
}

function applyProcessEvent(event) {
  if (event.type === "start") {
    state.currentRunId = event.runId || "";
    state.currentOutputDir = event.outputDir || "";
    state.progress = {
      total: event.total || state.files.length,
      processed: 0,
      success: 0,
      failed: 0,
    };
    els.resultTitle.textContent = t("currentTask");
    els.quotaText.textContent = t("processingStart", { total: state.progress.total });
    els.processBtn.textContent = state.progress.total > 0 ? t("removingProgress", { processed: 0, total: state.progress.total }) : t("removingStart");
    setProgress(0);
    renderQueue();
    updateTaskActions();
    return;
  }

  if (event.type === "item") {
    state.progress = {
      total: event.total || state.files.length,
      processed: event.index || state.results.length + 1,
      success: event.success || 0,
      failed: event.failed || 0,
    };
    const queueIndex = Math.max((event.index || state.results.length + 1) - 1, 0);
    appendResult(event.item, queueIndex);
    const total = state.progress.total || 1;
    setProgress((state.progress.processed / total) * 100);
    els.quotaText.textContent = t("completedBatch", { success: state.progress.success, failed: state.progress.failed, outputDir: `${state.progress.processed}/${total}`, failure: "" });
    els.processBtn.textContent = t("removingProgress", { processed: state.progress.processed, total });
    return;
  }

  if (event.type === "done") {
    state.currentRunId = event.runId || state.currentRunId;
    state.currentOutputDir = event.outputDir || state.currentOutputDir;
    if (state.results.length === 0 && Array.isArray(event.items)) {
      state.results = event.items.map((item, index) => withQueueIndex(item, index));
    }
    state.progress = {
      total: event.total || state.results.length,
      processed: event.total || state.results.length,
      success: event.success || 0,
      failed: event.failed || 0,
    };
    setProgress(100);
    els.quotaText.textContent = completedBatchMessage(event.success, event.failed, event.outputDir);
    els.processBtn.textContent = t("finalizing");
    renderQueue();
    updateTaskActions();
  }
}

async function readProcessStream(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) {
        applyProcessEvent(JSON.parse(line));
      }
    }
    if (done) {
      break;
    }
  }

  if (buffer.trim()) {
    applyProcessEvent(JSON.parse(buffer));
  }
}

async function readProcessJson(response) {
  const data = await response.json();
  state.results = (data.items || []).map((item, index) => withQueueIndex(item, index));
  state.currentRunId = data.runId || state.currentRunId;
  state.currentOutputDir = data.outputDir || state.currentOutputDir;
  state.progress = {
    total: data.total || state.results.length,
    processed: data.total || state.results.length,
    success: data.success || 0,
    failed: data.failed || 0,
  };
  setProgress(100);
  els.quotaText.textContent = completedBatchMessage(data.success, data.failed, data.outputDir);
  renderQueue();
  updateTaskActions();
}

function resetProcessingView() {
  state.results = [];
  if (state.selectedIndex < 0 && state.files.length > 0) {
    state.selectedIndex = 0;
  }
  state.progress = { total: state.files.length, processed: 0, success: 0, failed: 0 };
  setProgress(0);
  renderQueue();
}

async function processFiles() {
  if (state.processing || state.files.length === 0) return;
  state.processing = true;
  document.body.classList.add("is-processing");
  renderSelection();
  els.processBtn.textContent = t("uploading");
  els.quotaText.textContent = t("submitting", { count: state.files.length });
  resetProcessingView();

  const settings = currentSettings();
  const form = new FormData();
  form.append("processingMode", settings.processingMode);
  form.append("outputFormat", settings.outputFormat);
  form.append("edgeOptimize", String(settings.edgeOptimize));
  form.append("transparentBackground", String(settings.transparentBackground));
  form.append("backgroundColor", settings.backgroundColor);
  for (const entry of state.files) {
    form.append("paths", encodeURIComponent(relativeName(entry)));
    form.append("files", entry.file, entry.file.name);
  }

  try {
    const response = await fetch("/api/process", {
      method: "POST",
      headers: { Accept: "application/x-ndjson" },
      body: form,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      if (response.status === 403) throw new Error(t("tokenExpired"));
      if (response.status === 413) throw new Error(data.error || t("uploadTooLarge"));
      const detail = data.detail ? `（${data.detail}）` : "";
      const suggestion = data.suggestion ? ` ${data.suggestion}` : t("checkServerLogs");
      throw new Error(t("requestFailed", { status: response.status, error: data.error || t("noErrorDetail"), detail, suggestion }));
    }
    const contentType = response.headers.get("Content-Type") || "";
    if (response.body && contentType.includes("application/x-ndjson")) {
      await readProcessStream(response);
    } else {
      await readProcessJson(response);
    }
  } catch (error) {
    els.quotaText.textContent = error.message;
    setProgress(0);
  } finally {
    state.processing = false;
    document.body.classList.remove("is-processing");
    els.processBtn.textContent = t("startRemoval");
    renderSelection();
    renderQueue();
    await loadHistorySummary();
  }
}

async function openResultFolder(item) {
  if (!item.ok || !item.outputPath) return;
  try {
    const response = await fetch("/api/open-result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: item.outputPath }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || t("unableOpenResults"));
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
    if (!response.ok) throw new Error(data.error || t("unableOpenCurrentResults"));
  } catch (error) {
    els.quotaText.textContent = error.message;
  }
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    els.statusText.textContent = t(runtimeStateText[data.runtimeState] || "ready");
    els.statusText.classList.toggle("ready", data.runtimeState === "ready");
    if (data.modelsDir) els.modelsDirectory.textContent = data.modelsDir;
  } catch (error) {
    els.statusText.textContent = t("serviceUnavailable");
  }
}

function showRuntimeToast(message) {
  window.clearTimeout(runtimeToastTimer);
  els.runtimeToast.textContent = message;
  els.runtimeToast.hidden = !message;
  if (!message) return;
  runtimeToastTimer = window.setTimeout(() => {
    els.runtimeToast.hidden = true;
    els.runtimeToast.textContent = "";
  }, 3000);
}

async function selectRuntime() {
  const identifier = els.modelSelect.value;
  const provider = els.providerSelect.value;
  if (!identifier) return false;
  const previous = state.activeModel;
  els.modelSelect.dataset.switching = "true";
  els.modelSelect.disabled = true;
  els.statusText.textContent = t("modelLoading");
  let response;
  try {
    response = await fetch("/api/runtime/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: identifier, provider }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data.detail ? `（${data.detail}）` : "";
      throw new Error(`${data.error || t("modelSwitchFailed")}${detail}`);
    }
    state.activeModel = data.active;
    els.modelSelect.value = data.active;
    els.statusText.textContent = t("ready");
    els.statusText.classList.add("ready");
    showRuntimeToast(t("modelSwitchSuccess", { model: data.active, provider, seconds: Number(data.loadSeconds || 0).toFixed(3) }));
    return true;
  } catch (error) {
    els.modelSelect.value = previous;
    els.statusText.textContent = t("modelSwitchFailed");
    els.statusText.classList.remove("ready");
    showRuntimeToast(response?.status === 409 ? t("switchAfterProcessing") : error.message);
    return false;
  } finally {
    delete els.modelSelect.dataset.switching;
    els.modelSelect.disabled = state.processing || els.modelSelect.options.length === 0;
    els.providerSelect.disabled = els.modelSelect.disabled;
  }
}

async function loadRuntimeControls() {
  try {
    const response = await fetch("/api/models");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
    const models = Array.isArray(data.models) ? data.models : [];
    const providersResponse = await fetch("/api/providers");
    const providersData = await providersResponse.json().catch(() => ({}));
    els.modelSelect.replaceChildren();
    for (const model of models) {
      const option = document.createElement("option");
      option.value = model.id;
      option.textContent = model.id;
      els.modelSelect.appendChild(option);
    }
    if (models.length === 0) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = t("noModelInFolder");
      els.modelSelect.appendChild(option);
      els.modelSelect.disabled = true;
      els.modelHelp.hidden = false;
      return;
    }
    state.activeModel = data.active || models[0].id;
    els.modelSelect.value = state.activeModel;
    els.providerSelect.replaceChildren();
    for (const provider of providersData.providers || []) {
      const option = document.createElement("option");
      option.value = provider.id;
      option.textContent = provider.label;
      els.providerSelect.appendChild(option);
    }
    els.providerSelect.value = providersData.selected || "auto";
    els.modelSelect.disabled = false;
    els.providerSelect.disabled = false;
    els.modelHelp.hidden = true;
  } catch (error) {
    els.modelSelect.replaceChildren();
    const option = document.createElement("option");
    option.value = "";
    option.textContent = t("unableReadModels");
    els.modelSelect.appendChild(option);
    els.modelSelect.disabled = true;
    els.quotaText.textContent = error.message;
  }
}

function historySummaryUrl(olderThanDays = 0) {
  let url = `/api/tasks/history?protectRunId=${encodeURIComponent(state.currentRunId)}`;
  if (olderThanDays) url += `&olderThanDays=${olderThanDays}`;
  return url;
}

function setHistoryFeedback(message, tone = "neutral") {
  els.historyFeedback.textContent = message;
  els.historyFeedback.hidden = !message;
  els.historyFeedback.dataset.tone = tone;
}

function historyStatusText(task) {
  if (task.status === "running") return t("running");
  if (task.failed > 0) return t("completedWithFailed", { count: task.failed });
  return t("completed");
}

function updateHistorySelection() {
  const deletable = state.historyTasks.filter((task) => task.canDelete);
  const selected = deletable.filter((task) => state.selectedHistoryRunIds.has(task.runId));
  els.selectAllHistory.disabled = deletable.length === 0;
  els.selectAllHistory.checked = deletable.length > 0 && selected.length === deletable.length;
  els.selectAllHistory.indeterminate = selected.length > 0 && selected.length < deletable.length;
  els.deleteSelectedTasksBtn.disabled = selected.length === 0;
  els.deleteSelectedTasksBtn.textContent = selected.length ? t("deleteSelectedCount", { count: selected.length }) : t("deleteSelected");
}

function renderHistoryTasks(tasks) {
  state.historyTasks = Array.isArray(tasks) ? tasks : [];
  const available = new Set(state.historyTasks.filter((task) => task.canDelete).map((task) => task.runId));
  state.selectedHistoryRunIds = new Set(
    [...state.selectedHistoryRunIds].filter((runId) => available.has(runId)),
  );
  els.historyTaskList.replaceChildren();
  if (state.historyTasks.length === 0) {
    const empty = document.createElement("div");
    empty.className = "history-task-empty";
    empty.textContent = t("noHistory");
    els.historyTaskList.appendChild(empty);
    updateHistorySelection();
    return;
  }

  for (const task of state.historyTasks) {
    const card = document.createElement("article");
    card.className = "history-task-card";
    card.classList.toggle("is-current", task.runId === state.currentRunId);

    const check = document.createElement("input");
    check.className = "history-task-check";
    check.type = "checkbox";
    check.disabled = !task.canDelete;
    check.checked = state.selectedHistoryRunIds.has(task.runId);
    check.setAttribute("aria-label", t("selectTask", { runId: task.runId }));
    check.addEventListener("change", () => {
      if (check.checked) state.selectedHistoryRunIds.add(task.runId);
      else state.selectedHistoryRunIds.delete(task.runId);
      updateHistorySelection();
    });

    const info = document.createElement("div");
    info.className = "history-task-info";
    const title = document.createElement("strong");
    title.textContent = task.createdAt || task.runId;
    title.title = task.runId;
    const meta = document.createElement("span");
    meta.textContent =
      `${historyStatusText(task)} · ${task.total || 0} · ${formatBytes(task.sizeBytes)}` +
      (task.runId === state.currentRunId ? t("currentViewing") : "");
    info.append(title, meta);

    const actions = document.createElement("div");
    actions.className = "history-task-actions";
    const viewButton = document.createElement("button");
    viewButton.type = "button";
    viewButton.textContent = t("view");
    viewButton.addEventListener("click", () => viewHistoryTask(task.runId));
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "delete-task";
    deleteButton.textContent = t("delete");
    deleteButton.disabled = !task.canDelete;
    deleteButton.title = task.canDelete ? t("deleteTask") : t("cannotDeleteTask");
    deleteButton.addEventListener("click", () => deleteHistoryRuns([task.runId]));
    actions.append(viewButton, deleteButton);
    card.append(check, info, actions);
    els.historyTaskList.appendChild(card);
  }
  updateHistorySelection();
}

function renderHistorySummary(data) {
  els.historySummary.textContent = t("taskSummary", { count: data.totalTasks || 0, size: formatBytes(data.totalBytes) });
  renderHistoryTasks(data.tasks || []);
}

async function loadHistorySummary() {
  try {
    const response = await fetch(historySummaryUrl());
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderHistorySummary(await response.json());
  } catch (error) {
    els.historySummary.textContent = t("unableHistorySummary");
    setHistoryFeedback(t("loadHistoryFailed", { error: error.message }), "error");
  }
}

async function viewHistoryTask(runId) {
  try {
    setHistoryFeedback(t("loadingTask"), "working");
    const response = await fetch(`/api/tasks/${encodeURIComponent(runId)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || t("taskLoadFailed"));
    restoreTask(data.task);
    els.resultTitle.textContent = t("selectedHistoryTask");
    setHistoryFeedback(t("loadedTask", { runId }), "success");
    await loadHistorySummary();
  } catch (error) {
    setHistoryFeedback(t("viewFailed", { error: error.message }), "error");
  }
}

async function deleteHistoryRuns(runIds) {
  if (!runIds.length) return;
  const confirmed = window.confirm(t("deleteConfirm", { count: runIds.length }));
  if (!confirmed) {
    setHistoryFeedback(t("deletionCancelled"), "neutral");
    return;
  }
  try {
    setHistoryFeedback(t("deletingTasks", { count: runIds.length }), "working");
    const response = await fetch("/api/tasks/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true, runIds, protectRunId: state.currentRunId }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || t("deleteHistoryFailed"));
    state.selectedHistoryRunIds.clear();
    setHistoryFeedback(
      t("deletedTasks", { count: result.deletedTasks, size: formatBytes(result.freedBytes) }),
      "success",
    );
    await loadHistorySummary();
  } catch (error) {
    setHistoryFeedback(t("deleteFailed", { error: error.message }), "error");
  }
}

function deleteSelectedTasks() {
  return deleteHistoryRuns([...state.selectedHistoryRunIds]);
}

async function quickCleanupHistory(days) {
  try {
    setHistoryFeedback(t("checkingOldTasks", { days }), "working");
    const previewResponse = await fetch(historySummaryUrl(days));
    const preview = await previewResponse.json();
    if (!previewResponse.ok) throw new Error(preview.error || t("cleanupPreviewFailed"));
    if (!preview.cleanupTasks) {
      setHistoryFeedback(t("noCleanupTasks", { days }), "success");
      return;
    }
    const confirmed = window.confirm(
      t("cleanupConfirm", { count: preview.cleanupTasks, days, size: formatBytes(preview.cleanupBytes) }),
    );
    if (!confirmed) {
      setHistoryFeedback(t("cleanupCancelled"), "neutral");
      return;
    }
    setHistoryFeedback(t("cleaningTasks", { days }), "working");
    const response = await fetch("/api/tasks/cleanup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        confirm: true,
        olderThanDays: days,
        protectRunId: state.currentRunId,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || t("quickCleanupFailed"));
    state.selectedHistoryRunIds.clear();
    setHistoryFeedback(
      t("cleanedTasks", { count: result.deletedTasks, size: formatBytes(result.freedBytes) }),
      "success",
    );
    await loadHistorySummary();
  } catch (error) {
    setHistoryFeedback(t("cleanupFailed", { error: error.message }), "error");
  }
}

function cleanupHistory() {
  return quickCleanupHistory(30);
}

function restoreTask(task) {
  if (!task || !Array.isArray(task.items) || task.items.length === 0) return;
  state.currentRunId = task.runId || "";
  state.currentOutputDir = task.outputDir || "";
  state.files = task.items.map((item) => ({
    file: null,
    path: item.inputName || item.outputName || "image",
    inputUrl: item.inputUrl || "",
  }));
  state.results = task.items.map((item, index) => withQueueIndex(item, index));
  const firstOk = state.results.findIndex((item) => item.ok);
  state.selectedIndex = firstOk >= 0 ? firstOk : 0;
  state.progress = {
    total: task.total || state.results.length,
    processed: task.total || state.results.length,
    success: task.success || 0,
    failed: task.failed || 0,
  };
  setProgress(state.progress.total > 0 ? (state.progress.processed / state.progress.total) * 100 : 0);
  els.quotaText.textContent = t("restoredTask", { runId: state.currentRunId });
  renderSelection();
  renderQueue();
}

async function loadRecentTask() {
  if (state.files.length > 0 || state.processing) return;
  try {
    const response = await fetch("/api/tasks/recent?limit=1");
    if (!response.ok) return;
    const data = await response.json();
    restoreTask(data.latest || (data.tasks || [])[0]);
  } catch (error) {
    // 静态预览或服务未就绪时忽略，避免影响上传入口。
  }
}

function clearAll() {
  state.files = [];
  state.results = [];
  state.selectedIndex = -1;
  state.currentRunId = "";
  state.currentOutputDir = "";
  state.progress = { total: 0, processed: 0, success: 0, failed: 0 };
  els.singleFileInput.value = "";
  els.fileInput.value = "";
  els.folderInput.value = "";
  setProgress(0);
  els.quotaText.textContent = "";
  renderSelection();
  renderQueue();
  loadHistorySummary();
}

function resetSettings() {
  const rmbgInput = document.querySelector('input[name="processingMode"][value="rmbg"]');
  if (rmbgInput) {
    rmbgInput.checked = true;
  }
  const pngInput = document.querySelector('input[name="outputFormat"][value="png"]');
  if (pngInput) {
    pngInput.checked = true;
  }
  els.edgeOptimize.checked = true;
  els.transparentBackground.checked = true;
  els.backgroundColor.value = "#ffffff";
  els.backgroundColorText.value = "#FFFFFF";
  updateFormatMeta();
}

function syncColorInputs(source) {
  const normalized = normalizeHex(source.value);
  els.backgroundColor.value = normalized;
  els.backgroundColorText.value = normalized;
  updateFormatMeta();
}

function bindImageDropTarget(target) {
  ["dragenter", "dragover"].forEach((eventName) => {
    target.addEventListener(eventName, (event) => {
      event.preventDefault();
      target.classList.add("dragging");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    target.addEventListener(eventName, (event) => {
      event.preventDefault();
      target.classList.remove("dragging");
    });
  });

  target.addEventListener("drop", (event) => {
    collectDroppedEntries(event.dataTransfer)
      .then(setEntries)
      .catch(() => setFiles(event.dataTransfer.files));
  });
}

els.chooseSingleBtn.addEventListener("click", () => els.singleFileInput.click());
els.chooseFilesBtn.addEventListener("click", () => els.fileInput.click());
els.chooseFolderBtn.addEventListener("click", () => els.folderInput.click());
els.singleFileInput.addEventListener("change", (event) => setFiles(event.target.files));
els.fileInput.addEventListener("change", (event) => setFiles(event.target.files));
els.folderInput.addEventListener("change", (event) => setFiles(event.target.files));
els.processBtn.addEventListener("click", processFiles);
els.rerunBtn.addEventListener("click", processFiles);
els.clearBtn.addEventListener("click", resetSettings);
els.clearListBtn.addEventListener("click", clearAll);
els.refreshHistoryBtn.addEventListener("click", loadHistorySummary);
els.deleteSelectedTasksBtn.addEventListener("click", deleteSelectedTasks);
els.selectAllHistory.addEventListener("change", () => {
  state.selectedHistoryRunIds.clear();
  if (els.selectAllHistory.checked) {
    for (const task of state.historyTasks) {
      if (task.canDelete) state.selectedHistoryRunIds.add(task.runId);
    }
  }
  renderHistoryTasks(state.historyTasks);
});
document.querySelectorAll("[data-cleanup-days]").forEach((button) => {
  button.addEventListener("click", () => quickCleanupHistory(Number(button.dataset.cleanupDays)));
});
els.openOutputBtn.addEventListener("click", openCurrentRunFolder);
els.openOutputBtnBottom.addEventListener("click", openCurrentRunFolder);
els.themeToggleBtn.addEventListener("click", toggleTheme);
document.querySelectorAll("[data-language]").forEach((button) => {
  button.addEventListener("click", () => applyLanguage(button.dataset.language, true));
});
els.modelSelect.addEventListener("change", selectRuntime);
els.providerSelect.addEventListener("change", selectRuntime);

preferredThemeQuery.addEventListener("change", (event) => {
  if (!storedTheme()) {
    applyTheme(event.matches ? "dark" : "light");
  }
});

document.querySelectorAll('input[name="outputFormat"]').forEach((input) => {
  input.addEventListener("change", updateFormatMeta);
});
document.querySelectorAll('input[name="processingMode"]').forEach((input) => {
  input.addEventListener("change", updateFormatMeta);
});
els.edgeOptimize.addEventListener("change", updateFormatMeta);
els.transparentBackground.addEventListener("change", updateFormatMeta);
els.backgroundColor.addEventListener("input", () => syncColorInputs(els.backgroundColor));
els.backgroundColorText.addEventListener("change", () => syncColorInputs(els.backgroundColorText));
bindImageDropTarget(els.dropZone);
bindImageDropTarget(els.originalUploadZone);
document.addEventListener("paste", handleImagePaste);

applyLanguage(initialLanguage());
loadStatus().then(loadRuntimeControls);
loadRecentTask().then(loadHistorySummary);
updateFormatMeta();
renderQueue();

async function collectDroppedEntries(dataTransfer) {
  const items = Array.from(dataTransfer.items || []);
  const entries = items
    .map((item) => (item.webkitGetAsEntry ? item.webkitGetAsEntry() : null))
    .filter(Boolean);
  if (entries.length === 0) {
    return Array.from(dataTransfer.files || []).map((file) => makeEntry(file));
  }

  const collected = [];
  for (const entry of entries) {
    const nested = await walkEntry(entry, "");
    collected.push(...nested);
  }
  return collected;
}

function walkEntry(entry, prefix) {
  if (entry.isFile) {
    return new Promise((resolve, reject) => {
      entry.file(
        (file) => resolve([makeEntry(file, `${prefix}${file.name}`)]),
        reject
      );
    });
  }
  if (entry.isDirectory) {
    const reader = entry.createReader();
    const folder = `${prefix}${entry.name}/`;
    return readAllDirectoryEntries(reader).then(async (children) => {
      const collected = [];
      for (const child of children) {
        const nested = await walkEntry(child, folder);
        collected.push(...nested);
      }
      return collected;
    });
  }
  return Promise.resolve([]);
}

function readAllDirectoryEntries(reader) {
  const entries = [];
  return new Promise((resolve, reject) => {
    const readBatch = () => {
      reader.readEntries(
        (batch) => {
          if (batch.length === 0) {
            resolve(entries);
            return;
          }
          entries.push(...batch);
          readBatch();
        },
        reject
      );
    };
    readBatch();
  });
}
