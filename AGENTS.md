# AI CAD Workbench — orientações do repositório

- O produto principal é o servidor MCP consumido por agentes externos (Claude Code, Codex, Cursor). A IA embutida (chat DeepSeek) foi removida; não reintroduza chat interno nem provedores de modelo dentro do Workbench.
- M0 a M7 formam a baseline concluída. Não há próximo marco automático; trabalho novo entra como manutenção ou incremento explicitamente aprovado.
- O fluxo normal usa o FreeCAD 1.1.1 instalado no Windows e abre o Workbench pelo próprio FreeCAD. Os scripts de inicialização são apenas auxiliares de desenvolvimento.
- Mantenha o FreeCAD como adaptador; regras de produto e schemas não devem depender dele.
- Painel e MCP devem chamar o mesmo `ToolRegistry`.
- Toda mutação CAD deve ser transacional, validada e reversível.
- Não adicione uma ferramenta que execute Python arbitrário.
- Nunca grave chaves, tokens ou credenciais em arquivos do projeto.
- Código importável fora do FreeCAD deve continuar testável sem a instalação do FreeCAD.
- Execute `scripts/testar.ps1` antes de considerar uma alteração concluída.
