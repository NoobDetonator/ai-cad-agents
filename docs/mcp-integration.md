# Integração MCP

O agente externo é a IA. O servidor `aicad-mcp` expõe ferramentas estruturadas e
envia a execução para o Workbench aberto no FreeCAD.

## Pré-requisitos

- FreeCAD 1.1.1 aberto com o Workbench **AI CAD** ativo;
- `.venv` preparada conforme [installation.md](installation.md);
- executável `.venv\Scripts\aicad-mcp.exe` disponível.

Sem a GUI, apenas `health`, `available_cad_tools` e `available_cad_recipes`
funcionam. Operações CAD retornam erro controlado de ponte indisponível.

## Configuração

O repositório já contém `.mcp.json` para Claude Code. Registro manual:

```powershell
claude mcp add ai-cad -- <projeto>\.venv\Scripts\aicad-mcp.exe
```

Codex, em `~/.codex/config.toml`:

```toml
[mcp_servers.ai-cad]
command = "C:\\caminho\\do\\projeto\\.venv\\Scripts\\aicad-mcp.exe"
```

Cursor, em `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "ai-cad": {
      "command": "C:/caminho/do/projeto/.venv/Scripts/aicad-mcp.exe"
    }
  }
}
```

## Fluxo recomendado

1. Liste capacidades com `available_cad_tools` ou receitas com
   `available_cad_recipes`.
2. Leia `cad.get_context_snapshot` por `execute_cad_read_tool`.
3. Resolva objetos e meça o que for relevante.
4. Para uma mutação, use `request_cad_tool` e repita o mesmo `request_id` até o
   estado terminal.
5. Para duas a oito mutações, prefira `submit_cad_plan` e acompanhe com
   `get_cad_plan_status`.
6. Valide o documento e meça o resultado.
7. Capture com `cad.capture_view`; use `view="isometric"` e `fit=true` para
   enquadrar o modelo inteiro.
8. Exporte STL ou STEP somente para um destino autorizado pelo usuário.

Receitas disponíveis: `mounting_plate`, `flange`, `rectangular_pad`,
`stepped_shaft` e `flat_pulley`.

## Comportamentos importantes

- mutações seguem a opção de aprovação visível no painel;
- exportações são sempre manuais;
- argumentos inválidos falham antes da geometria;
- referências ambíguas nunca são escolhidas por palpite;
- erros de domínio retornam uma causa curta e redigida;
- operações longas podem levar mais de um minuto;
- `cad.undo` desfaz a última transação confirmada;
- toda ação entra na auditoria local.

`cad.create_through_hole` atravessa o sólido inteiro por padrão. Para furar
somente um ressalto, informe `z_min` e `z_max` em coordenadas globais.

## Problemas comuns

| Sintoma | Ação |
| --- | --- |
| Ponte indisponível | abrir o FreeCAD e ativar **AI CAD** |
| `pending_confirmation` parado | responder no painel ou habilitar aceitação automática |
| Ferramenta desconhecida | atualizar `available_cad_tools` |
| Objeto ambíguo | selecionar ou informar nome único |
| Arquivo de exportação existente | usar `overwrite=true` apenas com autorização |
