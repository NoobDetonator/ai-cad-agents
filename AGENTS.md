# AI CAD Workbench — orientações do repositório

- O produto principal é o servidor MCP consumido por agentes externos (Claude Code, Codex, Cursor). A IA embutida (chat DeepSeek) foi removida; não reintroduza chat interno nem provedores de modelo dentro do Workbench.
- M0 a M7 formam a baseline concluída. O trabalho de capacidade segue o plano P em `docs/partdesign-roadmap.md` (Part Design paramétrico via reflexão governada); frentes E1 pendentes ficam adiadas até o P concluir.
- `.study/` contém repositórios de terceiros clonados para análise (fora do Git). Nunca copie código de lá sem revisar licença e segurança; as conclusões vivem em `docs/estudo-freecad-mcp.md`.
- O fluxo normal usa o FreeCAD 1.1.1 instalado no Windows e abre o Workbench pelo próprio FreeCAD. Os scripts de inicialização são apenas auxiliares de desenvolvimento.
- Mantenha o FreeCAD como adaptador; regras de produto e schemas não devem depender dele.
- Painel e MCP devem chamar o mesmo `ToolRegistry`.
- Toda mutação CAD deve ser transacional, validada e reversível.
- Não adicione uma ferramenta que execute Python arbitrário.
- Nunca grave chaves, tokens ou credenciais em arquivos do projeto.
- Código importável fora do FreeCAD deve continuar testável sem a instalação do FreeCAD.
- Execute `scripts/testar.ps1` antes de considerar uma alteração concluída.
