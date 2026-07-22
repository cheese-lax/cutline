#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

test -x .venv/bin/python || { echo "Run ./scripts/install_linux.sh first." >&2; exit 1; }
test -f model.onnx || { echo "Model not found: $project_root/model.onnx" >&2; exit 1; }

exec .venv/bin/python rmbg_onnx_runner/web_app.py \
  --model model.onnx \
  --output-dir outputs \
  --provider auto \
  --open \
  "$@"
