# Repository Guidelines

## Project Structure & Module Organization

Core Python code lives in `rmbg_onnx_runner/`. `web_app.py` exposes the localhost Flask service, `task_service.py` manages jobs and history, `runtime.py` selects platform/runtime behavior, and `rmbg_onnx.py` contains ONNX image processing. Browser assets are plain HTML, CSS, and JavaScript under `rmbg_onnx_runner/web/`. Tests are colocated in `rmbg_onnx_runner/tests/` and use the `test_*.py` pattern. Platform installers and launchers live in `scripts/`; dependency sets are split by platform in `requirements/`. GitHub workflows are under `.github/workflows/`. Do not commit model weights, virtual environments, or generated `outputs/` data.

## Build, Test, and Development Commands

Use Python 3.11–3.13 from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements/dev.txt
.venv/bin/pytest
.venv/bin/ruff check .
```

`pytest` runs the complete suite; `ruff check .` enforces imports and selected Python errors. Run `.venv/bin/python rmbg_onnx_runner/web_app.py --help` to smoke-test the CLI. For local use, run `./scripts/install_macos.sh` and `./scripts/start_macos.sh` on macOS, or the matching Linux/Windows scripts. A compatible `model.onnx` is required for actual inference but not for most tests.

## Coding Style & Naming Conventions

Use four-space indentation, type hints where practical, and a 110-character Python line limit. Follow Ruff's configured `E4`, `E7`, `E9`, `F`, and `I` rules. Name functions and variables `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`, and tests `test_<behavior>`. Keep browser code dependency-free and consistent with the existing two-space JavaScript/CSS indentation.

## Testing Guidelines

Tests use pytest. Add focused unit tests beside the related suite and prefer temporary directories or mocked sessions over real model inference. Cover success, validation, and security-boundary cases. No numeric coverage threshold is configured; regressions must still include a test. Before submitting, run pytest, Ruff, and the CLI smoke check.

## Commit & Pull Request Guidelines

History uses concise imperative subjects with prefixes such as `feat:`, `fix:`, `docs:`, `ci:`, `build:`, and `refactor:`. Keep each commit scoped. Pull requests should explain behavior changes, list verification commands and platforms, link relevant issues, and include screenshots for UI changes. Call out provider-specific effects (CPU, CUDA, or CoreML) and any unverified platform.

## Security & Configuration

Keep the service bound to loopback only. Preserve access-token, Host/Origin, and response-header protections. Never commit ONNX weights, local images, generated results, credentials, or private vulnerability details; follow `SECURITY.md` for reporting.
