# Instalação local com o FreeCAD do Windows

O fluxo normal usa o FreeCAD 1.1.1 instalado no computador. Depois da vinculação
única do Workbench, o aplicativo pode ser aberto pelo menu Iniciar ou pelo atalho
normal do FreeCAD; `scripts/iniciar.ps1` não é necessário no uso diário.

## Instalação validada neste computador

- FreeCAD: `C:\Program Files\FreeCAD 1.1\bin\FreeCAD.exe`;
- FreeCADCmd: `C:\Program Files\FreeCAD 1.1\bin\FreeCADCmd.exe`;
- Python do FreeCAD: 3.11;
- projeto: `C:\Users\HRBASSIST55\Downloads\Ai-Cad Agents`.

Os caminhos são exemplos da máquina validada. O código não depende deles: o
Workbench descobre a raiz do checkout a partir da própria instalação vinculada.

## Preparar as dependências Python

O servidor MCP usa o ambiente `.venv` do projeto. Se ele ainda não existir,
execute uma vez, na raiz do repositório:

```powershell
& "C:\Program Files\FreeCAD 1.1\bin\python.exe" -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install --no-build-isolation -e ".[dev]"
```

O antigo `scripts/setup.ps1` continua disponível somente como alternativa de
desenvolvimento reproduzível com uma cópia portátil do FreeCAD. Ele não é
necessário quando o FreeCAD instalado e a `.venv` já existem.

## Vincular o Workbench uma única vez

Feche o FreeCAD e execute na raiz do projeto:

```powershell
$project = (Resolve-Path .).Path
$modRoot = Join-Path $env:APPDATA "FreeCAD\v1-1\Mod"
$workbench = Join-Path $modRoot "AiCad"
New-Item -ItemType Directory -Force -Path $modRoot | Out-Null
New-Item -ItemType Junction -Path $workbench `
  -Target (Join-Path $project "src\freecad\AiCad")
```

O comando cria apenas um vínculo de diretório; não duplica o projeto. Se já
existir algo em `AiCad`, confira o destino antes de substituir ou remover.

## Abrir normalmente

1. Abra **FreeCAD 1.1.1** pelo menu Iniciar.
2. Escolha o Workbench **AI CAD** na lista.
3. O painel lateral deve abrir à direita e publicar a ponte MCP automaticamente.
4. Teste `resumo` no chat local ou chame `health` pelo cliente MCP.

O painel inicia com **Aceitar automaticamente as alterações** marcado para
mutações locais, da IA e do MCP. A opção é visível e pode ser desmarcada para
restaurar confirmação manual. Exportações sempre exigem confirmação visual. O
`scripts/iniciar_rapido.ps1` permanece como auxiliar do ambiente portátil.

## Atualizar ou remover

Como o Workbench é um vínculo para o checkout, atualizar o repositório atualiza o
código usado na próxima abertura do FreeCAD. Para remover a integração, feche o
FreeCAD e remova somente o junction `%APPDATA%\FreeCAD\v1-1\Mod\AiCad`; os arquivos do
repositório permanecem intactos.

## Diagnóstico

| Sintoma | Verificação |
| --- | --- |
| **AI CAD** não aparece | Confirmar que `%APPDATA%\FreeCAD\v1-1\Mod\AiCad\InitGui.py` existe pelo junction |
| Erro ao importar `aicad` | Confirmar `src\aicad` no projeto e a `.venv` criada com Python 3.11 |
| Dependência ausente | Repetir a instalação editável na `.venv` |
| Ponte MCP indisponível | Ativar o Workbench **AI CAD** e manter o FreeCAD aberto |
