# Instalação

O uso normal depende do FreeCAD 1.1.1 instalado no Windows. Depois de vincular o
Workbench uma vez, abra o FreeCAD pelo menu Iniciar; scripts de inicialização são
apenas auxiliares de desenvolvimento.

## 1. Criar o ambiente Python

Na raiz do projeto:

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install --no-build-isolation -e ".[dev]"
```

O caminho pode variar conforme a instalação do FreeCAD.

## 2. Vincular o Workbench

Feche o FreeCAD e execute:

```powershell
$project = (Resolve-Path .).Path
$modRoot = Join-Path $env:APPDATA "FreeCAD\v1-1\Mod"
$workbench = Join-Path $modRoot "AiCad"
New-Item -ItemType Directory -Force -Path $modRoot | Out-Null
New-Item -ItemType Junction -Path $workbench `
  -Target (Join-Path $project "src\freecad\AiCad")
```

Se `AiCad` já existir, confira seu destino antes de remover ou substituir.

## 3. Abrir

1. Abra o FreeCAD 1.1.1.
2. Selecione o Workbench **TALOS MCP**.
3. Confirme que o painel apareceu à direita.
4. Confirme "Ponte MCP ativa" no painel e teste `health` pelo MCP.

O painel inicia exigindo confirmação visual de cada mutação. Defina
`TALOS_AUTO_APPROVE=1` (ou marque a opção no painel) para aprovar
automaticamente apenas mutações compensáveis; exportações e operações não
reversíveis continuam exigindo confirmação manual.

## Atualização

O junction aponta para o checkout atual. Depois de atualizar o Git, reinicie o
FreeCAD para carregar o novo código. Para remover a integração, feche o FreeCAD
e remova somente `%APPDATA%\FreeCAD\v1-1\Mod\AiCad`.

## Diagnóstico

| Problema | Verificação |
| --- | --- |
| Workbench não aparece | conferir o junction e `InitGui.py` |
| Falha ao importar `aicad` | recriar a `.venv` com Python 3.11 e reinstalar o projeto |
| Ponte indisponível | ativar o Workbench **TALOS MCP** e manter o FreeCAD aberto |
| Dependência ausente | repetir a instalação editável na `.venv` |
