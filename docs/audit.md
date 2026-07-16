# Auditoria local

A auditoria explica o que foi pedido, planejado, autorizado e executado sem
guardar a conversa completa, credenciais ou código arbitrário.

## Conteúdo de uma ação

| Grupo | Dados |
| --- | --- |
| Identidade | versão, sessão, ação, revisão, origem e horário |
| Entendimento | pedido isolado, intenção e suposições |
| Plano | ID, hash, estado-base e passos exibidos |
| Chamadas | ferramenta, argumentos validados, risco e validações |
| Aprovação | pendente, manual, automática, negada ou cancelada |
| Resultado | estado, duração, resultado seguro ou código de erro |
| CAD | commit, abort, undo e ordem das transações |

O mesmo `action_id` recebe revisões monotônicas durante seu ciclo de vida. Uma
falha de auditoria impede que uma ação nova seja aceita silenciosamente.

## Armazenamento

Por padrão, os registros ficam na pasta de dados do usuário:

```text
ai-cad-workbench/audit/v1/<session_id>/<action_id>.json
```

`AICAD_AUDIT_DIR` permite outro diretório para teste ou instalação administrada.
O caminho não deve ficar dentro do repositório. Escritas são atômicas, arquivos
simbólicos são recusados e permissões ficam limitadas ao usuário.

## Redaction

Antes de gravar ou exportar, o serviço remove:

- chaves, senhas, tokens, cookies e credenciais;
- valores `Bearer` e atribuições sensíveis em texto;
- binários e tipos secretos;
- caminhos absolutos dentro de pastas pessoais.

Payloads grandes, profundos, não serializáveis ou com números não finitos falham
fechados. `state_token` é estado do documento e não é removido; tokens de sessão
ou autenticação sempre são.

## Retenção

Padrão: 90 dias, 50 sessões e 1.000 ações por sessão. A limpeza atua somente no
namespace versionado e nunca segue links simbólicos.

## Consulta e exportação

- `cad.get_audit_history`: resumo limitado da sessão atual;
- `cad.export_audit_history`: bundle completo e redigido.

A exportação exige destino explícito, confirmação manual e `overwrite=true` para
substituir um arquivo. O bundle registra também a própria ação de exportação.

## Cobertura

Testes unitários cobrem contrato, revisões, redaction, retenção e exportação. O
smoke gráfico valida ações reais de chat, MCP, planos, commits e undos.
