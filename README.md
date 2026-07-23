# Cutline ONNX

<p align="center">
  <img src="docs/assets/cutline-logo.png" width="148" alt="Cutline logo" />
</p>

<p align="center"><strong>An offline AI image background-removal tool</strong></p>

<p align="center">
  <a href="README_ZH.md">Chinese</a> | <strong>English</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-172033.svg" alt="MIT License" /></a>
  <img src="https://img.shields.io/badge/python-3.11--3.13-2DD4BF.svg" alt="Python 3.11 to 3.13" />
  <img src="https://img.shields.io/badge/runtime-ONNX-FF6B5E.svg" alt="ONNX Runtime" />
</p>

**Cutline** runs ONNX-compatible background-removal models on your own computer. Your images, models, and results stay local; the browser is only a localhost control panel. The UI defaults to English and includes a **中文 | English** language switcher.

## Interface preview

### Light theme

![Cutline light interface](docs/assets/cutline-ui-light.jpg)

### Dark theme

![Cutline dark interface](docs/assets/cutline-ui-dark.jpg)

## Why Cutline

- **Local first:** the service listens only on `127.0.0.1`; source images, models, and results are not uploaded.
- **Batch processing:** process one image, multiple images, or a folder recursively. Results and task history can be restored.
- **Controllable output:** PNG, WebP, JPG, and AVIF; transparent backgrounds, a background color, and edge optimization.
- **Cross-platform inference:** automatic selection of CPU, NVIDIA CUDA, or macOS CoreML, with manual selection available.
- **Two modes:** smart removal uses an ONNX model; line-art mode needs no model and suits signatures or simple drawings.

## Quick start

> Python 3.12 is recommended. CPU mode supports Python 3.11–3.13; Windows CUDA is best used with Python 3.12.

1. Download an RMBG-2.0 ONNX model you are authorized to use and place it in `models/` at the project root.
2. Install the dependencies for your platform.
3. Run the startup script. It opens the local interface in your browser.

```text
models/
  model_fp16.onnx
```

Model sources: [Hugging Face](https://huggingface.co/briaai/RMBG-2.0) · [ModelScope](https://www.modelscope.cn/models/AI-ModelScope/RMBG-2.0). This repository does not contain model weights. Read [third-party and model notices](THIRD_PARTY_NOTICES.md) before use.

## Install dependencies

Run these commands from the project root.

### Windows + NVIDIA CUDA

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements\windows-cuda.txt
```

### Windows CPU

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r .\requirements\cpu.txt
```

### macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements/macos.txt
```

### Linux CPU or NVIDIA CUDA

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements/cpu.txt
# For NVIDIA CUDA, use requirements/linux-cuda.txt instead.
```

## Start the app

```text
Windows: .\scripts\start_windows.ps1
macOS:   ./scripts/start_macos.sh
Linux:   ./scripts/start_linux.sh
```

The startup scripts choose an available runtime and open the browser. Press `Ctrl+C` in the terminal to stop the service.

Use the interface as follows:

1. Choose a model from `models/`, then choose Smart removal or Line art.
2. Add images or choose a folder.
3. Configure output format, transparency, background color, and edge optimization.
4. Start processing, preview the results, then download them or open the results folder.

Results are written to `outputs/<task-id>/results/`. Refreshing the page restores the most recent task.

## Runtime and troubleshooting

The web service and the inference worker are separate processes. When you switch a model or provider, Cutline waits for the previous inference process to stop before starting the next one. It does not accept new work during a switch, and tries to restore the previous model if the new one fails to load.

If no model is present, the UI still opens and shows the absolute `models/` folder plus a download link for [RMBG-2.0 ONNX](https://huggingface.co/briaai/RMBG-2.0/tree/main/onnx). Confirm the model license before downloading or using it.

Providers are automatic detection, CPU, NVIDIA CUDA, and Apple CoreML. CoreML may use CPU, GPU, or ANE and may fall back to CPU; it is not a GPU-only mode.

The service reports available memory and process RSS when a run fails. It reports CUDA free/total VRAM when measurable. Error wording describes possible causes unless a Python `MemoryError` confirms the cause.

Common checks:

- **No model found:** put at least one `.onnx` file in `models/`, or specify `--model`.
- **CUDA unavailable:** use Python 3.12, verify NVIDIA drivers, and check for `CUDAExecutionProvider`; try `--provider cpu` first.
- **Browser does not open:** stop the service, set a default browser, then restart.
- **Port already in use:** the app tries later ports, or pass `--port` explicitly.

## Parameters and environment checks

| Parameter | Default | Description |
| --- | --- | --- |
| `--models-dir` | `models` | Directory listed in the UI |
| `--model` | automatic | Optional initial model path |
| `--output-dir` | `outputs` | Results directory |
| `--provider` | `auto` | `auto`, `cpu`, `cuda`, or `coreml` |
| `--port` | `8765` | Local port |
| `--max-upload-mb` | `1024` | Maximum upload size in MB |

```bash
.venv/bin/python rmbg_onnx_runner/web_app.py --help
.venv/bin/python rmbg_onnx_runner/check_env.py --model models/model_fp16.onnx --provider auto
```

## Security and licensing

The service binds to `127.0.0.1` only. Do not expose it to a LAN or the internet through a reverse proxy. Read [SECURITY.md](SECURITY.md) for the security policy.

The source code is under the [MIT License](LICENSE). Model weights follow their own licenses and are not downloaded or distributed by this project. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Development and tests

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements/dev.txt
.venv/bin/pytest
.venv/bin/ruff check .
```
