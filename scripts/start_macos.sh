#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

test -x .venv/bin/python || { echo "Run ./scripts/install_macos.sh first." >&2; exit 1; }
test -d models || { echo "Models directory not found: $project_root/models" >&2; exit 1; }

exec .venv/bin/python rmbg_onnx_runner/web_app.py \
  --models-dir models \
  --output-dir outputs \
  --provider auto \
  --open \
  "$@"
