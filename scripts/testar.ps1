$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Runtime = Join-Path $ProjectRoot ".runtime"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FreeCadCmdFile = Join-Path $Runtime "freecadcmd-exe.txt"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Ambiente Python ausente. Execute .\scripts\setup.ps1."
}

Push-Location $ProjectRoot
try {
    & $VenvPython -m pytest
    if ($LASTEXITCODE -ne 0) {
        throw "Os testes unitarios falharam."
    }
    if (Test-Path -LiteralPath $FreeCadCmdFile) {
        $FreeCadCmd = (Get-Content -Raw $FreeCadCmdFile).Trim()
        $env:AICAD_PROJECT_ROOT = $ProjectRoot
        $freeCadOutput = & $FreeCadCmd -M (Join-Path $ProjectRoot "src\freecad") `
            -P (Join-Path $ProjectRoot "src") `
            (Join-Path $ProjectRoot "tests\freecad_smoke.py") 2>&1
        $freeCadOutput | ForEach-Object { Write-Host $_ }
        $freeCadText = $freeCadOutput -join "`n"
        if ($LASTEXITCODE -ne 0 -or $freeCadText -notmatch "FREECAD_SMOKE_OK") {
            throw "O teste de integracao com o FreeCAD falhou."
        }
    }
} finally {
    Pop-Location
}
