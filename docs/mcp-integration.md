# Integração MCP

O agente externo é a IA. O servidor `aicad-mcp` expõe ferramentas estruturadas e
envia a execução para o Workbench aberto no FreeCAD.

## Pré-requisitos

- FreeCAD 1.1.1 aberto com o Workbench **AI CAD** ativo;
- `.venv` preparada conforme [installation.md](installation.md);
- executável `.venv\Scripts\aicad-mcp.exe` disponível.

Sem a GUI, `health`, descoberta de capacidades e receitas funcionam normalmente.
Operações CAD retornam erro controlado de ponte indisponível.

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

1. Busque cartões compactos com `search_cad_capabilities` ou receitas com
   `available_cad_recipes`.
2. Carregue os contratos escolhidos com `describe_cad_capabilities`.
3. Leia `cad.get_context_snapshot` por `execute_cad_read_tool`.
4. Resolva objetos e meça o que for relevante.
5. Para uma mutação, use `request_cad_tool` e repita o mesmo `request_id` até o
   estado terminal.
6. Para duas a oito mutações, prefira `submit_cad_plan` e acompanhe com
   `get_cad_plan_status`.
7. Valide o documento e meça o resultado.
8. Capture com `cad.capture_view`; use `view="isometric"` e `fit=true` para
   enquadrar o modelo inteiro.
9. Exporte STL ou STEP somente para um destino autorizado pelo usuário.

`search_cad_capabilities` aceita consulta vazia para paginação estável, filtros
`families` e `risks`, `limit` de até 20 e `cursor`. O resultado não inclui schemas
e permanece pequeno. `describe_cad_capabilities` aceita até 16 nomes únicos e
preserva a ordem pedida. `available_cad_tools` é o endpoint completo legado.

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
| Ferramenta desconhecida | refazer `search_cad_capabilities` e descrever o contrato escolhido |
| Objeto ambíguo | selecionar ou informar nome único |
| Arquivo de exportação existente | usar `overwrite=true` apenas com autorização |
