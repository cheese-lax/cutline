from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

import onnxruntime as ort

if hasattr(ort, "preload_dlls"):
    ort.preload_dlls(directory="")

from rmbg_onnx import choose_providers


def run_nvidia_smi() -> str:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return f"nvidia-smi unavailable: {exc}"
    return completed.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check RMBG-2.0 ONNX runtime environment.")
    parser.add_argument("--model", default="model.onnx", help="Optional ONNX model path to inspect.")
    parser.add_argument("--provider", choices=["cuda", "auto", "cpu"], default="cuda")
    args = parser.parse_args()

    print(f"platform: {platform.platform()}")
    print(f"python: {sys.version.split()[0]}")
    print(f"onnxruntime: {ort.__version__}")
    print(f"available providers: {ort.get_available_providers()}")
    print(f"selected providers: {choose_providers(args.provider)}")
    print(f"nvidia-smi: {run_nvidia_smi()}")

    model_path = Path(args.model)
    if model_path.exists():
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        session = ort.InferenceSession(
            str(model_path),
            sess_options=session_options,
            providers=choose_providers(args.provider),
        )
        print(f"model: {model_path.resolve()}")
        print(f"session providers: {session.get_providers()}")
        for item in session.get_inputs():
            print(f"input: name={item.name}, type={item.type}, shape={item.shape}")
        for item in session.get_outputs():
            print(f"output: name={item.name}, type={item.type}, shape={item.shape}")
    else:
        print(f"model not found, skipped model inspection: {model_path.resolve()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
