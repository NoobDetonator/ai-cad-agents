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
$GuiSmokeTimeoutSeconds = 60
$env:AICAD_VISUAL_CACHE = Join-Path $Runtime "visual-cache"

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
            ('"' + (Join-Path $ProjectRoot "tests\freecad_gui_smoke.py") + '"')
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
            }
            Get-CimInstance Win32_Process |
                Where-Object {
                    $_.Name -eq "FreeCAD.exe" -and
                    $_.CommandLine -like "*freecad_gui_smoke.py*"
                } |
                ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
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
