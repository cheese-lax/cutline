#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

python3 -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)' \
  || { echo "Python 3.11-3.13 is required." >&2; exit 1; }
test -x .venv/bin/python || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip uninstall -y onnxruntime-gpu >/dev/null 2>&1 || true
.venv/bin/python -m pip install -r requirements/macos.txt
.venv/bin/python rmbg_onnx_runner/check_env.py --provider auto --model model.onnx

echo "Environment ready. Run ./scripts/start_macos.sh"
