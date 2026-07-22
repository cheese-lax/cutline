[CmdletBinding()]
param(
    [string]$Model = "model.onnx",
    [string]$OutputDir = "outputs",
    [ValidateSet("auto", "cuda", "coreml", "cpu")]
    [string]$Provider = "auto",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Environment missing. Run scripts\install_windows.ps1 first."
}
if (-not (Test-Path $Model)) {
    throw "Model not found: $Model"
}

& $Python rmbg_onnx_runner\web_app.py `
    --model $Model `
    --output-dir $OutputDir `
    --provider $Provider `
    --open `
    @ExtraArgs
exit $LASTEXITCODE
