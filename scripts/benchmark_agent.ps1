[CmdletBinding()]
param(
    [ValidateSet("markdown", "json")]
    [string]$Format = "markdown",
    [string]$Corpus
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Ambiente Python ausente. Execute .\scripts\setup.ps1 uma vez."
}

$PreviousPythonUtf8 = $env:PYTHONUTF8
$PreviousOutputEncoding = [Console]::OutputEncoding
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$PythonArguments = @("-m", "aicad.evaluation.benchmark", "--format", $Format)
if ($Corpus) {
    $PythonArguments += @("--corpus", $Corpus)
}

Push-Location $ProjectRoot
try {
    & $VenvPython @PythonArguments
    if ($LASTEXITCODE -ne 0) {
        throw "O benchmark offline do agente falhou."
    }
} finally {
    Pop-Location
    $env:PYTHONUTF8 = $PreviousPythonUtf8
    [Console]::OutputEncoding = $PreviousOutputEncoding
}
