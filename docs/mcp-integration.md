# Integração MCP com agentes externos

Este guia conecta um agente de IA — Claude Code, Codex, Cursor ou qualquer
cliente MCP — ao FreeCAD por meio do servidor `aicad-mcp`. O agente é o
cérebro; o servidor expõe apenas ferramentas estruturadas, validadas e
reversíveis. Nenhum texto do modelo é executado como código.

## Pré-requisitos

1. Ambiente preparado uma única vez com `.\scripts\setup.ps1`.
2. FreeCAD aberto pelo lançador do projeto, com o Workbench **AI CAD** ativo:

   ```powershell
   .\scripts\iniciar.ps1
   ```

   A GUI publica a sessão autenticada da ponte no runtime local do usuário.
   Sem a GUI aberta, as leituras e mutações retornam um erro controlado
   ("The FreeCAD GUI bridge is unavailable"); apenas `health`,
   `available_cad_tools` e `available_cad_recipes` funcionam offline.

O executável do servidor é criado pelo setup em
`.venv\Scripts\aicad-mcp.exe` e conversa por stdio.

## Claude Code

O repositório já contém um `.mcp.json` na raiz. Abrindo o Claude Code dentro
da pasta do projeto, o servidor `ai-cad` é oferecido automaticamente
(aprove-o quando solicitado). Para registrar manualmente em outro diretório:

```powershell
claude mcp add ai-cad -- <caminho-do-projeto>\.venv\Scripts\aicad-mcp.exe
```

## Codex

Adicione ao `~/.codex/config.toml`:

```toml
[mcp_servers.ai-cad]
command = "C:\\caminho\\do\\projeto\\.venv\\Scripts\\aicad-mcp.exe"
```

## Cursor

Crie (ou complemente) `.cursor/mcp.json` no projeto que usará o CAD:

```json
{
  "mcpServers": {
    "ai-cad": {
      "command": "C:/caminho/do/projeto/.venv/Scripts/aicad-mcp.exe"
    }
  }
}
```

## Como o agente deve trabalhar

1. **Descobrir capacidades**: `available_cad_tools` lista as 30 ferramentas
   com schema, risco, aliases e exemplos; `available_cad_recipes` lista as
   receitas confiáveis com parâmetros tipados.
2. **Ler antes de agir**: `execute_cad_read_tool` executa qualquer ferramenta
   de risco `read` imediatamente — comece por
   `cad.get_context_snapshot` para obter o estado versionado do documento.
3. **Uma mutação**: `request_cad_tool` com uma ferramenta `modify` retorna
   `pending_confirmation`; o usuário decide no painel do FreeCAD. Repita a
   chamada com o mesmo `request_id` para consultar o desfecho (polling
   idempotente).
4. **Plano de 2 a 8 mutações**: `submit_cad_plan` congela o plano com hash e
   estado-base e o usuário aprova tudo com uma única confirmação;
   `get_cad_plan_status` acompanha o progresso e `cancel_cad_plan` desiste.
   Falha no meio do plano dispara rollback compensatório verificado.
5. **Receitas**: `submit_cad_recipe` compila `mounting_plate`, `flange` ou
   `rectangular_pad` em um plano revisável — prefira uma receita quando ela
   cobre o pedido.
6. **Verificar o resultado**: `cad.measure_object` confere dimensões e
   `cad.capture_view` devolve um `capture_id`; o PNG sai pelo resource
   `aicad://view/{capture_id}`. Use esse loop para se autocorrigir.
7. **Exportar**: `cad.export_stl` ou `cad.export_step` via `request_cad_tool`,
   com destino absoluto escolhido pelo usuário. A exportação valida o
   documento antes, nunca sobrescreve sem `overwrite=true`, exige confirmação
   visual e devolve tamanho e SHA-256 do arquivo.

Um fluxo completo típico: contexto → plano aprovado (placa + furos) → medidas
→ captura → `cad.export_stl` → arquivo pronto para fatiar.

## Comportamentos que o agente deve esperar

- Toda mutação e exportação aguarda confirmação humana no painel; avise o
  usuário para olhar o FreeCAD quando receber `pending_confirmation`.
- Argumentos fora do schema falham antes de qualquer execução, com mensagem
  explícita — corrija e reenvie.
- Referências ambíguas de objeto retornam erro ou `awaiting_selection` em vez
  de adivinhar.
- `cad.undo` desfaz a última transação; features derivadas guardam seus
  objetos de origem.
- Todas as ações ficam registradas no histórico auditável local, com
  redaction de segredos e caminhos pessoais.

## Solução de problemas

| Sintoma | Causa provável | Ação |
| --- | --- | --- |
| "The FreeCAD GUI bridge is unavailable" | FreeCAD fechado ou Workbench AI CAD inativo | Abrir com `.\scripts\iniciar.ps1` e ativar o Workbench |
| `pending_confirmation` nunca conclui | Confirmação não respondida no painel | Decidir no painel; requests expiram com timeout controlado |
| Exportação recusada com destino existente | Proteção de sobrescrita | Repetir com `overwrite: true` somente com autorização do usuário |
| Ferramenta desconhecida | Catálogo desatualizado no agente | Rechamar `available_cad_tools` |
