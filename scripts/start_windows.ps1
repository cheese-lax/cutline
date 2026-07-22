[CmdletBinding()]
param(
    [string]$ModelsDir = "models",
    [string]$Model = "",
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
if (-not (Test-Path $ModelsDir -PathType Container)) {
    throw "Models directory not found: $ModelsDir"
}

$WebArgs = @(
    "rmbg_onnx_runner\web_app.py",
    "--models-dir", $ModelsDir,
    "--output-dir", $OutputDir,
    "--provider", $Provider,
    "--open"
)
if ($Model) {
    $WebArgs += @("--model", $Model)
}

& $Python @WebArgs @ExtraArgs
exit $LASTEXITCODE
