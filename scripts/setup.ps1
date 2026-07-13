[CmdletBinding()]
param(
    [string]$FreeCadVersion = "1.1.1"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Downloads = Join-Path $ProjectRoot ".downloads"
$Tools = Join-Path $ProjectRoot ".tools"
$Runtime = Join-Path $ProjectRoot ".runtime"
$Venv = Join-Path $ProjectRoot ".venv"

New-Item -ItemType Directory -Force -Path $Downloads, $Tools, $Runtime | Out-Null

Write-Host "Consultando a versão oficial do FreeCAD $FreeCadVersion..."
$headers = @{ "User-Agent" = "ai-cad-workbench-setup" }
$releaseUrl = "https://api.github.com/repos/FreeCAD/FreeCAD/releases/tags/$FreeCadVersion"
$release = Invoke-RestMethod -Headers $headers -Uri $releaseUrl
$asset = $release.assets | Where-Object {
    $_.name -match "Windows-x86_64.*\.7z$" -and $_.name -notmatch "SHA256"
} | Select-Object -First 1

if (-not $asset) {
    throw "Pacote portátil do FreeCAD para Windows x86_64 não encontrado."
}

$archive = Join-Path $Downloads $asset.name
if (-not (Test-Path -LiteralPath $archive)) {
    Write-Host "Baixando $($asset.name) ($([math]::Round($asset.size / 1MB)) MB)..."
    Invoke-WebRequest -Headers $headers -Uri $asset.browser_download_url -OutFile $archive
}

$checksumAsset = $release.assets | Where-Object {
    $_.name -eq "$($asset.name)-SHA256.txt"
} | Select-Object -First 1
if ($checksumAsset) {
    $checksumFile = Join-Path $Downloads $checksumAsset.name
    Invoke-WebRequest -Headers $headers -Uri $checksumAsset.browser_download_url -OutFile $checksumFile
    $expected = ((Get-Content -Raw $checksumFile) -split "\s+")[0].Trim().ToLowerInvariant()
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "Falha na verificação SHA256 do FreeCAD."
    }
    Write-Host "Arquivo oficial verificado por SHA256."
}

$FreeCadRoot = Join-Path $Tools "freecad-$FreeCadVersion"
if (-not (Test-Path -LiteralPath $FreeCadRoot)) {
    Write-Host "Extraindo FreeCAD..."
    New-Item -ItemType Directory -Force -Path $FreeCadRoot | Out-Null
    & tar.exe -xf $archive -C $FreeCadRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Falha ao extrair o pacote 7z do FreeCAD."
    }
}

$FreeCadExe = Get-ChildItem -LiteralPath $FreeCadRoot -Recurse -Filter "FreeCAD.exe" |
    Select-Object -First 1 -ExpandProperty FullName
$FreeCadCmd = Get-ChildItem -LiteralPath $FreeCadRoot -Recurse -Filter "FreeCADCmd.exe" |
    Select-Object -First 1 -ExpandProperty FullName
$FreeCadPython = Join-Path (Split-Path -Parent $FreeCadExe) "bin\python.exe"
if (-not (Test-Path -LiteralPath $FreeCadPython)) {
    $FreeCadPython = Get-ChildItem -LiteralPath $FreeCadRoot -Recurse -Filter "python.exe" |
        Where-Object { $_.FullName -match "\\bin\\python\.exe$" } |
        Select-Object -First 1 -ExpandProperty FullName
}

if (-not $FreeCadExe -or -not $FreeCadCmd -or -not $FreeCadPython) {
    throw "Executáveis esperados não foram encontrados no pacote do FreeCAD."
}

Set-Content -Encoding UTF8 -Path (Join-Path $Runtime "freecad-exe.txt") -Value $FreeCadExe
Set-Content -Encoding UTF8 -Path (Join-Path $Runtime "freecadcmd-exe.txt") -Value $FreeCadCmd
Set-Content -Encoding UTF8 -Path (Join-Path $Runtime "freecad-python.txt") -Value $FreeCadPython

if (-not (Test-Path -LiteralPath $Venv)) {
    Write-Host "Criando ambiente Python isolado..."
    & $FreeCadPython -m venv $Venv
}

$VenvPython = Join-Path $Venv "Scripts\python.exe"
$env:PIP_USE_FEATURE = "truststore"
& $VenvPython -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao atualizar o instalador de pacotes Python."
}
& $VenvPython -m pip install --no-build-isolation -e "$ProjectRoot[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao instalar as dependencias Python do projeto."
}
& $VenvPython -m pip freeze | Set-Content -Encoding UTF8 (Join-Path $Runtime "installed-packages.txt")

Write-Host "Executando testes unitários..."
& $VenvPython -m pytest
if ($LASTEXITCODE -ne 0) {
    throw "Os testes unitarios falharam."
}

Write-Host "Ambiente preparado com sucesso."
Write-Host "Use .\scripts\iniciar.ps1 para abrir o AI CAD."
