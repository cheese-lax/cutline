$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".\model.onnx")) {
    Write-Warning "model.onnx not found in $PSScriptRoot. Put the FP32 model file here before running inference."
}

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    python -m venv .venv
}

$python = ".\.venv\Scripts\python.exe"
$mirror = "https://pypi.tuna.tsinghua.edu.cn/simple"

& $python -m pip install -U pip -i $mirror
& $python -m pip install -r requirements-win-gpu.txt -i $mirror
& $python -c "import onnxruntime as ort; print('onnxruntime', ort.__version__); print('providers', ort.get_available_providers())"

Write-Host ""
Write-Host "Environment ready. Next commands:"
Write-Host "  .\.venv\Scripts\python.exe .\check_env.py --model .\model.onnx --provider cuda"
Write-Host "  .\.venv\Scripts\python.exe .\web_app.py --model .\model.onnx --output-dir .\outputs --provider cuda --open"
Write-Host "  .\.venv\Scripts\python.exe .\run_rmbg_onnx.py --model .\model.onnx --input .\sample_input.png --provider cuda"
