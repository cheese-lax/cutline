[CmdletBinding()]
param(
    [ValidateSet("auto", "cuda", "cpu")]
    [string]$Runtime = "auto"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (Get-Command py -ErrorAction SilentlyContinue) {
    $PySelector = $null
    foreach ($Version in @("3.13", "3.12", "3.11")) {
        & py "-$Version" -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $PySelector = "-$Version"
            break
        }
    }
    if (-not $PySelector) {
        throw "Python 3.11-3.13 is required."
    }
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        & py $PySelector -m venv .venv
    }
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.11-3.13 is required."
    }
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        & python -m venv .venv
    }
} else {
    throw "Python was not found. Install Python 3.11-3.13 from python.org."
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
& $Python -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "The existing .venv does not use Python 3.11-3.13. Remove it and run this script again."
}

if ($Runtime -eq "auto") {
    $Runtime = if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { "cuda" } else { "cpu" }
}
$Requirements = if ($Runtime -eq "cuda") {
    "requirements\windows-cuda.txt"
} else {
    "requirements\cpu.txt"
}

& $Python -m pip install --upgrade pip
& $Python -m pip uninstall -y onnxruntime onnxruntime-gpu 2>$null
& $Python -m pip install -r $Requirements
& $Python rmbg_onnx_runner\check_env.py --provider auto --model model.onnx

Write-Host "Environment ready. Run scripts\start_windows.ps1"
