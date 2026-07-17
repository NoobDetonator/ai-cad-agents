$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Runtime = Join-Path $ProjectRoot ".runtime"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvSitePackages = Join-Path $ProjectRoot ".venv\Lib\site-packages"
$FreeCadCmdFile = Join-Path $Runtime "freecadcmd-exe.txt"
$FreeCadExeFile = Join-Path $Runtime "freecad-exe.txt"
$FreeCadModule = Join-Path $ProjectRoot "src\freecad\AiCad"
$UserConfig = Join-Path $Runtime "test-user.cfg"
$SystemConfig = Join-Path $Runtime "test-system.cfg"
$PytestTemp = Join-Path $Runtime ("pytest-" + $PID)
$GuiSmokeTimeoutSeconds = 120
$env:AICAD_VISUAL_CACHE = Join-Path $Runtime "visual-cache"
$env:AICAD_AUDIT_DIR = Join-Path $Runtime "audit"
$env:TALOS_AUTO_APPROVE = "0"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "Ambiente Python ausente. Execute .\scripts\setup.ps1."
}

Push-Location $ProjectRoot
try {
& $VenvPython -m ruff check src tests
if ($LASTEXITCODE -ne 0) {
    throw "A verificacao estatica do Ruff falhou."
}
& $VenvPython -m mypy `
    src\aicad\core\schema_validation.py `
    src\aicad\core\tool_registry.py `
    src\aicad\core\transactions.py
if ($LASTEXITCODE -ne 0) {
    throw "A verificacao de tipos do nucleo falhou."
}

    New-Item -ItemType Directory -Force -Path $PytestTemp | Out-Null
    & $VenvPython -m pytest `
        --basetemp $PytestTemp `
        -p no:cacheprovider `
        --cov=aicad.core `
        --cov=aicad.bridge `
        --cov=aicad.audit `
        --cov=aicad.orchestration `
        --cov-fail-under=80
    if ($LASTEXITCODE -ne 0) {
        throw "Os testes unitarios falharam."
    }
    if (Test-Path -LiteralPath $FreeCadCmdFile) {
        $FreeCadCmd = (Get-Content -Raw $FreeCadCmdFile).Trim()
        $env:AICAD_PROJECT_ROOT = $ProjectRoot
        $freeCadOutput = & $FreeCadCmd -u $UserConfig -s $SystemConfig `
            -M $FreeCadModule `
            -P $VenvSitePackages `
            -P (Join-Path $ProjectRoot "src") `
            (Join-Path $ProjectRoot "tests\freecad_smoke.py") 2>&1
        $freeCadOutput | ForEach-Object { Write-Host $_ }
        $freeCadText = $freeCadOutput -join "`n"
        if ($LASTEXITCODE -ne 0 -or $freeCadText -notmatch "FREECAD_SMOKE_OK") {
            throw "O teste de integracao com o FreeCAD falhou."
        }
        $foundationOutput = & $FreeCadCmd -u $UserConfig -s $SystemConfig `
            -M $FreeCadModule `
            -P $VenvSitePackages `
            -P (Join-Path $ProjectRoot "src") `
            (Join-Path $ProjectRoot "tests\freecad_foundation_smoke.py") 2>&1
        $foundationOutput | ForEach-Object { Write-Host $_ }
        $foundationText = $foundationOutput -join "`n"
        if (
            $LASTEXITCODE -ne 0 -or
            $foundationText -notmatch "FREECAD_FOUNDATION_SMOKE_OK"
        ) {
            throw "O teste fundamental do FreeCAD falhou."
        }
        $sketchOutput = & $FreeCadCmd -u $UserConfig -s $SystemConfig `
            -M $FreeCadModule `
            -P $VenvSitePackages `
            -P (Join-Path $ProjectRoot "src") `
            (Join-Path $ProjectRoot "tests\freecad_sketch_smoke.py") 2>&1
        $sketchOutput | ForEach-Object { Write-Host $_ }
        $sketchText = $sketchOutput -join "`n"
        if (
            $LASTEXITCODE -ne 0 -or
            $sketchText -notmatch "FREECAD_SKETCH_SMOKE_OK"
        ) {
            throw "O teste completo do ambiente de Sketch falhou."
        }
        $assemblyOutput = & $FreeCadCmd -u $UserConfig -s $SystemConfig `
            -M $FreeCadModule `
            -P $VenvSitePackages `
            -P (Join-Path $ProjectRoot "src") `
            (Join-Path $ProjectRoot "tests\freecad_assembly_smoke.py") 2>&1
        $assemblyOutput | ForEach-Object { Write-Host $_ }
        $assemblyText = $assemblyOutput -join "`n"
        if (
            $LASTEXITCODE -ne 0 -or
            $assemblyText -notmatch "FREECAD_ASSEMBLY_SMOKE_OK"
        ) {
            throw "O teste de montagem mecanica do FreeCAD falhou."
        }
        $bearingOutput = & $FreeCadCmd -u $UserConfig -s $SystemConfig `
            -M $FreeCadModule `
            -P $VenvSitePackages `
            -P (Join-Path $ProjectRoot "src") `
            (Join-Path $ProjectRoot "tests\freecad_bearings_smoke.py") 2>&1
        $bearingOutput | ForEach-Object { Write-Host $_ }
        $bearingText = $bearingOutput -join "`n"
        if (
            $LASTEXITCODE -ne 0 -or
            $bearingText -notmatch "FREECAD_BEARINGS_SMOKE_OK"
        ) {
            throw "O teste especializado de rolamentos do FreeCAD falhou."
        }
        $m4Output = & $FreeCadCmd -u $UserConfig -s $SystemConfig `
            -M $FreeCadModule `
            -P $VenvSitePackages `
            -P (Join-Path $ProjectRoot "src") `
            (Join-Path $ProjectRoot "tests\freecad_m4_smoke.py") 2>&1
        $m4Output | ForEach-Object { Write-Host $_ }
        $m4Text = $m4Output -join "`n"
        if ($LASTEXITCODE -ne 0 -or $m4Text -notmatch "FREECAD_M4_SMOKE_OK") {
            throw "O teste mecanico M4 do FreeCAD falhou."
        }
        $m6Output = & $FreeCadCmd -u $UserConfig -s $SystemConfig `
            -M $FreeCadModule `
            -P $VenvSitePackages `
            -P (Join-Path $ProjectRoot "src") `
            (Join-Path $ProjectRoot "tests\freecad_m6_smoke.py") 2>&1
        $m6Output | ForEach-Object { Write-Host $_ }
        $m6Text = $m6Output -join "`n"
        if ($LASTEXITCODE -ne 0 -or $m6Text -notmatch "FREECAD_M6_SMOKE_OK") {
            throw "O teste de exportacao M6 do FreeCAD falhou."
        }
        $m7Output = & $FreeCadCmd -u $UserConfig -s $SystemConfig `
            -M $FreeCadModule `
            -P $VenvSitePackages `
            -P (Join-Path $ProjectRoot "src") `
            (Join-Path $ProjectRoot "tests\freecad_m7_smoke.py") 2>&1
        $m7Output | ForEach-Object { Write-Host $_ }
        $m7Text = $m7Output -join "`n"
        if ($LASTEXITCODE -ne 0 -or $m7Text -notmatch "FREECAD_M7_SMOKE_OK") {
            throw "O teste de documentos e modelagem M7 do FreeCAD falhou."
        }
    }
    if (Test-Path -LiteralPath $FreeCadExeFile) {
        $FreeCadExe = (Get-Content -Raw $FreeCadExeFile).Trim()
        $guiResult = Join-Path $Runtime "gui-smoke-result.txt"
        $guiScreenshot = Join-Path $Runtime "gui-smoke-panel.png"
        $guiLog = Join-Path $Runtime "gui-smoke.log"
        $env:AICAD_GUI_RESULT = $guiResult
        $env:AICAD_GUI_SCREENSHOT = $guiScreenshot
        $arguments = @(
            '-M', ('"' + $FreeCadModule + '"'),
            '-P', ('"' + (Join-Path $ProjectRoot "src") + '"'),
            '-u', ('"' + $UserConfig + '"'),
            '-s', ('"' + $SystemConfig + '"'),
            '--log-file', ('"' + $guiLog + '"'),
            ('"' + (Join-Path $ProjectRoot "tests\freecad_mcp_panel_smoke.py") + '"')
        )
        $startedAt = Get-Date
        $process = Start-Process -FilePath $FreeCadExe -ArgumentList $arguments -PassThru
        $deadline = $startedAt.AddSeconds($GuiSmokeTimeoutSeconds)
        $guiText = $null
        do {
            if (Test-Path -LiteralPath $guiResult) {
                $resultFile = Get-Item -LiteralPath $guiResult
                if ($resultFile.LastWriteTime -ge $startedAt) {
                    $guiText = (Get-Content -Raw -LiteralPath $guiResult).Trim()
                    break
                }
            }
            Start-Sleep -Milliseconds 250
        } while ((Get-Date) -lt $deadline)
        if (-not $guiText) {
            if (-not $process.HasExited) {
                $process.Kill()
                $process.WaitForExit(5000)
            }
            throw "O teste grafico do FreeCAD excedeu $GuiSmokeTimeoutSeconds segundos. Consulte $guiLog."
        }
        if ($guiText -ne "FREECAD_GUI_SMOKE_OK") {
            throw "O teste grafico do FreeCAD falhou: $guiText"
        }
        Write-Host $guiText
    }
} finally {
    Pop-Location
}
