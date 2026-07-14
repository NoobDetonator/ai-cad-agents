$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:AICAD_QUICK_TEST_MODE = "1"

& (Join-Path $ProjectRoot "scripts\iniciar.ps1")
