# Instala o TALOS de ponta a ponta usando o FreeCAD ja instalado:
# localiza o FreeCAD, cria a .venv com o Python dele, instala o projeto,
# vincula o Workbench no Mod do FreeCAD, grava os caminhos de runtime e
# imprime a configuracao MCP pronta para colar no agente.
[CmdletBinding()]
param(
    # Pasta bin do FreeCAD (ex.: "C:\Program Files\FreeCAD 1.1\bin").
    # Sem o parametro, o script procura em Program Files.
    [string]$FreeCadBin
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "== TALOS - instalacao =="

# --- 1. Localizar o FreeCAD ---------------------------------------------------
$candidates = @()
if ($FreeCadBin) { $candidates += $FreeCadBin }
$candidates += Get-ChildItem "C:\Program Files" -Directory -Filter "FreeCAD*" -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName "bin" }

$Bin = $null
foreach ($candidate in $candidates) {
    if ((Test-Path (Join-Path $candidate "python.exe")) -and
        (Test-Path (Join-Path $candidate "FreeCAD.exe"))) {
        $Bin = $candidate
        break
    }
}
if (-not $Bin) {
    throw ("FreeCAD nao encontrado. Instale o FreeCAD 1.1+ ou informe a pasta " +
        "bin: .\scripts\instalar.ps1 -FreeCadBin 'C:\caminho\FreeCAD\bin'")
}
$FreeCadPython = Join-Path $Bin "python.exe"
Write-Host "FreeCAD encontrado em: $Bin"

# --- 2. Ambiente Python -------------------------------------------------------
$Venv = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Criando .venv com o Python do FreeCAD..."
    & $FreeCadPython -m venv $Venv
}
Write-Host "Instalando o TALOS na .venv..."
& $VenvPython -m pip install --upgrade pip setuptools wheel --quiet
& $VenvPython -m pip install --no-build-isolation -e "$ProjectRoot[dev]" --quiet
if ($LASTEXITCODE -ne 0) { throw "A instalacao do pacote Python falhou." }

# --- 3. Vincular o Workbench --------------------------------------------------
$freecadData = Join-Path $env:APPDATA "FreeCAD"
$versionDir = Get-ChildItem $freecadData -Directory -Filter "v*" -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | Select-Object -First 1
if ($versionDir) { $modRoot = Join-Path $versionDir.FullName "Mod" }
else { $modRoot = Join-Path $freecadData "v1-1\Mod" }
New-Item -ItemType Directory -Force -Path $modRoot | Out-Null

$workbenchLink = Join-Path $modRoot "Talos"
$workbenchTarget = Join-Path $ProjectRoot "src\freecad\Talos"
if (Test-Path $workbenchLink) {
    $existing = Get-Item $workbenchLink
    if ($existing.LinkType -eq "Junction" -and $existing.Target -contains $workbenchTarget) {
        Write-Host "Workbench ja vinculado em $workbenchLink"
    } elseif ($existing.LinkType -eq "Junction") {
        Write-Host "Atualizando junction do Workbench..."
        $existing.Delete()
        New-Item -ItemType Junction -Path $workbenchLink -Target $workbenchTarget | Out-Null
    } else {
        throw ("$workbenchLink existe e nao e um junction. Remova manualmente " +
            "antes de reinstalar.")
    }
} else {
    New-Item -ItemType Junction -Path $workbenchLink -Target $workbenchTarget | Out-Null
    Write-Host "Workbench vinculado em $workbenchLink"
}

# --- 4. Caminhos de runtime (usados pelos scripts de dev e testes) -----------
$Runtime = Join-Path $ProjectRoot ".runtime"
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
Set-Content -Encoding UTF8 -Path (Join-Path $Runtime "freecad-exe.txt") -Value (Join-Path $Bin "FreeCAD.exe")
Set-Content -Encoding UTF8 -Path (Join-Path $Runtime "freecadcmd-exe.txt") -Value (Join-Path $Bin "FreeCADCmd.exe")
Set-Content -Encoding UTF8 -Path (Join-Path $Runtime "freecad-python.txt") -Value $FreeCadPython

# --- 5. Verificacao rapida ----------------------------------------------------
$probe = 'from talos.runtime import get_tool_registry as g; print(len(g().list_specs()))'
$toolCount = & $VenvPython -c $probe
if ($LASTEXITCODE -ne 0) { throw "O pacote talos nao importou corretamente." }
Write-Host "Catalogo carregado: $toolCount ferramentas."

# --- 6. Configuracao MCP ------------------------------------------------------
$ServerExe = Join-Path $Venv "Scripts\talos-freecad-mcp.exe"
$EscapedExe = $ServerExe.Replace('\', '\\')
Write-Host ""
Write-Host "== Pronto! Proximos passos =="
Write-Host "1. Abra o FreeCAD e selecione o Workbench 'TALOS MCP' (o painel publica a ponte)."
Write-Host "2. Conecte seu agente MCP:"
Write-Host ""
Write-Host "   Claude Code (deste diretorio, o .mcp.json do repositorio ja resolve), ou:"
Write-Host ('   claude mcp add talos -- "' + $ServerExe + '"')
Write-Host ""
Write-Host '   Configuracao JSON generica (Codex, Cursor e afins):'
Write-Host ('   {"mcpServers": {"talos": {"command": "' + $EscapedExe + '"}}}')
