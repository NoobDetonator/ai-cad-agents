# AI CAD Workbench — orientações do repositório

- Mantenha o FreeCAD como adaptador; regras de produto e schemas não devem depender dele.
- Chat interno e MCP devem chamar o mesmo `ToolRegistry`.
- Toda mutação CAD deve ser transacional, validada e reversível.
- Não adicione uma ferramenta que execute Python arbitrário.
- Nunca grave chaves, tokens ou credenciais em arquivos do projeto.
- Código importável fora do FreeCAD deve continuar testável sem a instalação do FreeCAD.
- Execute `scripts/testar.ps1` antes de considerar uma alteração concluída.
