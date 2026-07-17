$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:TALOS_AUTO_APPROVE = "1"

& (Join-Path $ProjectRoot "scripts\iniciar.ps1")
