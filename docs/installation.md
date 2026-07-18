# Instalação

Pré-requisito: FreeCAD 1.1+ instalado no Windows.

## Instalação em um comando

Na raiz do projeto:

```powershell
.\scripts\instalar.ps1
```

O script localiza o FreeCAD instalado (ou aceita
`-FreeCadBin "C:\caminho\FreeCAD\bin"`), cria a `.venv` com o Python do
FreeCAD, instala o TALOS, vincula o Workbench no `Mod` do FreeCAD, grava os
caminhos de runtime e imprime a configuração MCP pronta para o seu agente.

Depois disso:

1. Abra o FreeCAD e selecione o Workbench **TALOS MCP**.
2. Confirme "Ponte MCP ativa" no painel à direita.
3. Conecte o agente conforme [mcp-integration.md](mcp-integration.md).

O painel inicia exigindo confirmação visual de cada mutação. Defina
`TALOS_AUTO_APPROVE=1` (ou marque a opção no painel) para aprovar
automaticamente apenas mutações compensáveis; exportações e operações não
reversíveis continuam exigindo confirmação manual.

## Atualização

O junction aponta para o checkout atual: depois de atualizar o Git, reinicie o
FreeCAD. Se o `pyproject.toml` mudou, rode `.\scripts\instalar.ps1` de novo —
ele é idempotente.

Para remover a integração, feche o FreeCAD e apague somente
`%APPDATA%\FreeCAD\v1-1\Mod\Talos`.

## Instalação manual (equivalente ao script)

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-build-isolation -e ".[dev]"

$modRoot = Join-Path $env:APPDATA "FreeCAD\v1-1\Mod"
New-Item -ItemType Directory -Force -Path $modRoot | Out-Null
New-Item -ItemType Junction -Path (Join-Path $modRoot "Talos") `
  -Target (Join-Path (Resolve-Path .).Path "src\freecad\Talos")
```

## Diagnóstico

| Problema | Verificação |
| --- | --- |
| FreeCAD não encontrado | informe `-FreeCadBin` com a pasta `bin` da instalação |
| Workbench não aparece | conferir o junction em `%APPDATA%\FreeCAD\v*\Mod\Talos` |
| Falha ao importar `talos` | rodar `.\scripts\instalar.ps1` de novo |
| Ponte indisponível | ativar o Workbench **TALOS MCP** e manter o FreeCAD aberto |
