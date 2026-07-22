const state = {
  files: [],
  results: [],
  processing: false,
  selectedIndex: -1,
  selectedObjectUrl: "",
  currentRunId: "",
  currentOutputDir: "",
  progress: {
    total: 0,
    processed: 0,
    success: 0,
    failed: 0,
  },
};

const els = {
  statusText: document.querySelector("#statusText"),
  providerBadge: document.querySelector("#providerBadge"),
  openOutputBtn: document.querySelector("#openOutputBtn"),
  openOutputBtnBottom: document.querySelector("#openOutputBtnBottom"),
  dropZone: document.querySelector("#dropZone"),
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
  totalCount: document.querySelector("#totalCount"),
  processingCount: document.querySelector("#processingCount"),
  completedCount: document.querySelector("#completedCount"),
  pendingCount: document.querySelector("#pendingCount"),
  edgeOptimize: document.querySelector("#edgeOptimize"),
  transparentBackground: document.querySelector("#transparentBackground"),
  backgroundColor: document.querySelector("#backgroundColor"),
  backgroundColorText: document.querySelector("#backgroundColorText"),
  backgroundHint: document.querySelector("#backgroundHint"),
  processingModeHint: document.querySelector("#processingModeHint"),
  fileNameMeta: document.querySelector("#fileNameMeta"),
  resolutionMeta: document.querySelector("#resolutionMeta"),
  formatMeta: document.querySelector("#formatMeta"),
};

function supported(file) {
  return /^image\//.test(file.type) || /\.(jpe?g|png|webp|bmp|tiff?)$/i.test(file.name);
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
  return {
    processingMode,
    outputFormat: selectedOutputFormat(),
    edgeOptimize: els.edgeOptimize.checked,
    transparentBackground: processingMode === "line_art" || els.transparentBackground.checked,
    backgroundColor: normalizeHex(els.backgroundColorText.value || els.backgroundColor.value),
  };
}

function setFiles(files) {
  setEntries(Array.from(files).map((file) => makeEntry(file)));
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
  els.quotaText.textContent = `当前已选择 ${state.files.length} 张图片`;
  setProgress(0);
  renderSelection();
  renderQueue();
}

function renderSelection() {
  const hasFiles = state.files.length > 0;
  els.processBtn.disabled = !hasFiles || state.processing;
  els.rerunBtn.disabled = !hasFiles || state.processing;
  updateTaskActions();
}

function updateTaskActions() {
  const hasRun = Boolean(state.currentRunId);
  els.openOutputBtn.disabled = !hasRun;
  els.openOutputBtnBottom.disabled = !hasRun;
  const title = hasRun ? `打开 ${state.currentRunId} 的结果目录` : "完成一次抠图后可打开本次结果目录";
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
  };
  els.originalPreview.src = sourceUrl;
  els.originalPreview.alt = relativeName(entry);
  els.fileNameMeta.textContent = relativeName(entry);
}

function updateFormatMeta() {
  const settings = currentSettings();
  const lineArtMode = settings.processingMode === "line_art";
  const background = settings.transparentBackground ? "透明背景" : `${settings.backgroundColor} 背景`;
  els.formatMeta.textContent = lineArtMode
    ? `${settings.outputFormat.toUpperCase()}（线稿透明背景）`
    : `${settings.outputFormat.toUpperCase()}（${background}）`;
  els.edgeOptimize.disabled = lineArtMode;
  els.transparentBackground.disabled = lineArtMode;
  els.backgroundColor.disabled = lineArtMode || settings.transparentBackground;
  els.backgroundColorText.disabled = lineArtMode || settings.transparentBackground;
  els.processingModeHint.textContent = lineArtMode
    ? "自动识别背景色并按灰度差生成透明度，不使用抠图模型。背景区域将变为透明，线条颜色与细节会保留。"
    : "使用 RMBG 模型识别主体并移除背景";
  els.backgroundHint.textContent = lineArtMode
    ? "线稿模式始终输出透明背景"
    : settings.transparentBackground
    ? "仅在关闭透明背景时生效"
    : "将透明区域合成为所选背景色";
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
  card.title = "单击查看原图";
  card.innerHTML = `
    <div class="queue-thumb placeholder"></div>
    <div class="result-meta">
      <strong title="${relativeName(entry)}">${entry.file.name}</strong>
      <span>${status === "processing" ? "处理中" : "等待中"}</span>
    </div>
    <div class="card-state">${status === "processing" ? "处理中" : "待处理"}</div>
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
    card.title = "单击查看对比，双击打开图片所在文件夹";
    card.addEventListener("dblclick", () => openResultFolder(item));
  } else {
    thumb.textContent = "失败";
    card.title = "单击查看原图和失败信息";
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
  status.textContent = index === state.selectedIndex && item.ok ? "查看中" : item.ok ? "已完成" : "失败";
  card.appendChild(status);

  const openButton = document.createElement("button");
  openButton.className = "card-open";
  openButton.type = "button";
  openButton.textContent = item.ok ? "定位" : "-";
  openButton.disabled = !item.ok;
  openButton.addEventListener("click", (event) => {
    event.stopPropagation();
    openResultFolder(item);
  });
  card.appendChild(openButton);
  return card;
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
  els.resultPreview.src = item.outputUrl;
  els.resultPreview.alt = item.outputName || item.inputName;
  els.downloadFirstBtn.href = item.outputUrl;
  els.downloadFirstBtn.download = item.outputName;
  els.downloadFirstBtn.classList.remove("disabled");
}

function clearResultPreview() {
  els.resultPreview.removeAttribute("src");
  els.resultPreview.removeAttribute("alt");
  els.downloadFirstBtn.href = "#";
  els.downloadFirstBtn.classList.add("disabled");
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
    els.resultTitle.textContent = "批量任务";
    els.quotaText.textContent = `开始处理 ${state.progress.total} 张图片`;
    els.processBtn.textContent = state.progress.total > 0 ? `正在抠图 0/${state.progress.total}` : "正在抠图...";
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
    els.quotaText.textContent = `已完成 ${state.progress.processed}/${total}，成功 ${state.progress.success}，失败 ${state.progress.failed}`;
    els.processBtn.textContent = `正在抠图 ${state.progress.processed}/${total}`;
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
    els.quotaText.textContent = `完成 ${event.success} 张，失败 ${event.failed} 张；结果目录：${event.outputDir}`;
    els.processBtn.textContent = "正在收尾...";
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
  els.quotaText.textContent = `完成 ${data.success} 张，失败 ${data.failed} 张；结果目录：${data.outputDir}`;
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
  renderSelection();
  els.processBtn.textContent = "正在上传...";
  els.quotaText.textContent = `正在提交 ${state.files.length} 张图片`;
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
      if (response.status === 403) throw new Error("本地服务访问令牌已失效，请重新运行启动脚本。");
      if (response.status === 413) throw new Error(data.error || "上传内容超过服务限制。");
      throw new Error(data.error || "处理失败");
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
    els.processBtn.textContent = "开始抠图";
    renderSelection();
    renderQueue();
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
    if (!response.ok) throw new Error(data.error || "无法打开结果文件夹");
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
    if (!response.ok) throw new Error(data.error || "无法打开本次结果文件夹");
  } catch (error) {
    els.quotaText.textContent = error.message;
  }
}

async function loadStatus() {
  try {
    const response = await fetch("/api/status");
    const data = await response.json();
    const active = Array.isArray(data.providerActive) ? data.providerActive.join(" / ") : "CUDA";
    els.statusText.textContent = `模型已加载，${active}`;
    els.providerBadge.textContent = active;
    els.statusText.classList.add("ready");
  } catch (error) {
    els.statusText.textContent = "服务未就绪";
  }
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
  els.quotaText.textContent = `已恢复最近任务：${state.currentRunId}`;
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
  els.quotaText.textContent = "当前已选择 0 张图片";
  renderSelection();
  renderQueue();
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
els.openOutputBtn.addEventListener("click", openCurrentRunFolder);
els.openOutputBtnBottom.addEventListener("click", openCurrentRunFolder);

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

["dragenter", "dragover"].forEach((eventName) => {
  els.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropZone.classList.add("dragging");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  els.dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    els.dropZone.classList.remove("dragging");
  });
});

els.dropZone.addEventListener("drop", (event) => {
  collectDroppedEntries(event.dataTransfer)
    .then(setEntries)
    .catch(() => setFiles(event.dataTransfer.files));
});

loadStatus();
loadRecentTask();
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
