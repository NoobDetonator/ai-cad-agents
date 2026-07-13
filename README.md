# AI CAD Workbench

Base inicial de um ambiente CAD paramétrico controlável por chat interno e por MCP.

O primeiro protótipo usa o FreeCAD como motor de modelagem, visualização e documento. A camada `aicad` concentra ferramentas determinísticas, permissões, integração com IA e o futuro canal MCP.

## Estado atual

- Estrutura do Workbench do FreeCAD.
- Painel lateral de chat em modo de demonstração.
- Registro inicial de ferramentas CAD.
- Adaptador FreeCAD com leitura do documento e criação transacional de uma caixa.
- Servidor MCP mínimo para diagnóstico.
- Testes unitários e teste de fumaça dentro do FreeCAD.
- Instalação reproduzível e isolada para Windows.

## Preparação

Execute no PowerShell:

```powershell
.\scripts\setup.ps1
```

Depois, abra o FreeCAD com:

```powershell
.\scripts\iniciar.ps1
```

O ambiente `AI CAD` aparecerá na lista de Workbenches.

## Testes

```powershell
.\scripts\testar.ps1
```

## Segurança

Chaves de API nunca devem ser salvas no repositório. A integração usará o cofre de credenciais do sistema operacional. A pasta `.runtime` e os ambientes locais são ignorados pelo Git.

## Arquitetura

Consulte [docs/architecture.md](docs/architecture.md) e [docs/product-vision.md](docs/product-vision.md).
