# AI CAD Workbench

Base inicial de um ambiente CAD paramétrico controlável por chat interno e por MCP.

O primeiro protótipo usa o FreeCAD como motor de modelagem, visualização e documento. A camada `aicad` concentra ferramentas determinísticas, permissões, integração com IA e o futuro canal MCP.

## Estado atual

- Workbench `AI CAD` carregável pelo ambiente portátil já preparado.
- Painel lateral com chat local determinístico e sem dependência de provedor.
- Comandos para ler documento e seleção, validar, criar uma caixa e desfazer.
- Confirmação explícita na interface antes de criar ou desfazer.
- `ToolRegistry` único para catálogo, schemas, validação e política de risco.
- Chat e MCP conectados ao mesmo registro e ao mesmo adaptador.
- Criação de caixa em transação validada e registrada no histórico de desfazer.
- MCP com catálogo compartilhado e execução limitada a leitura nesta fase.
- Testes unitários, teste transacional no FreeCADCmd e teste gráfico automatizado.
- Instalação reproduzível e isolada para Windows.

## Preparação

Execute no PowerShell:

```powershell
.\scripts\setup.ps1
```

Se o ambiente já estiver preparado, não execute o setup novamente.

Depois, abra o FreeCAD com:

```powershell
.\scripts\iniciar.ps1
```

O ambiente `AI CAD` aparecerá na lista de Workbenches.

## Chat local

O painel aceita, nesta fase, um vocabulário fechado. Exemplos:

```text
resumo
seleção
validar
caixa 10 x 20 x 30 nome MinhaCaixa
desfazer
```

Leituras são executadas imediatamente. Criação e desfazer mostram o plano e só
executam depois do clique em **Confirmar operação**. Texto livre não vira Python
nem é enviado a um serviço externo.

## Testes

```powershell
.\scripts\testar.ps1
```

A suíte abre e fecha automaticamente uma instância isolada do FreeCAD para
confirmar que o Workbench aparece, o painel abre e o fluxo criar/desfazer funciona.

## Segurança

Chaves de API nunca devem ser salvas no repositório. Nenhuma chave é solicitada
na fase atual. Quando um provedor realmente for integrado, a credencial será
armazenada no cofre do Windows. A pasta `.runtime`, ambientes, downloads,
arquivos CAD gerados e segredos são ignorados pelo Git.

O MCP ainda não altera o documento: ele lista o catálogo compartilhado e pode
invocar apenas ferramentas marcadas como leitura. Mutações serão liberadas só
depois que a ponte com o processo gráfico puder pedir confirmação ao usuário na
thread principal do Qt.

## Arquitetura

Consulte [docs/architecture.md](docs/architecture.md),
[docs/product-vision.md](docs/product-vision.md) e
[docs/milestones.md](docs/milestones.md). O último contém o plano completo de
marcos e o roteiro para retomar o projeto em outro computador ou chat.
