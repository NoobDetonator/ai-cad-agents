# Auditoria local — contrato e armazenamento

Este documento registra as decisões do M5. O objetivo é
explicar, por ação, o que foi pedido, entendido, planejado, autorizado e
efetivamente concluído sem transformar o histórico em uma cópia integral da
conversa e sem gravar credenciais.

## Estado do marco

O M5 entrega um núcleo independente de FreeCAD, Qt, MCP e provedor:

- contrato Pydantic de auditoria na versão `1.0`;
- ID de sessão, ID de ação e revisões monotônicas do mesmo registro;
- pedido original isolado, intenção, suposições, plano e chamadas validadas;
- risco, decisão de aprovação, resultado, duração e validações;
- vínculo efetivo de cada chamada com commit, abort e undo do FreeCAD;
- redaction recursivo e limitado antes de toda gravação e exportação;
- armazenamento local atômico, com arquivos restritos ao usuário;
- retenção explícita e exportação sem sobrescrita silenciosa;
- integração com chat local, IA, MCP, planos simples e planos compostos;
- consulta e exportação pelo mesmo `ToolRegistry` usado para operações CAD.

Esse contrato permanece vigente na baseline M0–M7. As ferramentas adicionadas em
M6 e M7 — inclusive documentos, modelagem avançada e exportação STL/STEP — usam a
mesma sessão e a mesma trilha de auditoria. Não há próximo marco automático.

`AuditService` é criado uma vez por processo e compartilha seu `session_id` com a
sessão autenticada da ponte. Uma ação é persistida antes de entrar na fila ou
aguardar confirmação; sua revisão avança quando a autorização é decidida e quando
o resultado se torna terminal. Falha de auditoria impede que uma ação nova seja
aceita silenciosamente.

## Contrato `1.0`

Cada `AuditActionRecord` é um snapshot completo de uma única ação. O mesmo
`action_id` avança uma revisão por vez; identidade, sessão, origem, tipo e horário
inicial não podem mudar durante o ciclo de vida.

Os campos principais são:

| Grupo | Conteúdo |
| --- | --- |
| Identidade | versão, sessão, ação, revisão, origem e tipo |
| Entendimento | pedido original isolado, intenção e suposições |
| Plano | versão, ID, hash, estado-base e passos exibidos |
| Chamadas | ID, ferramenta registrada, argumentos validados, risco e validações esperadas |
| Autorização | pendente, dispensada, manual, automática, negada ou cancelada |
| Resultado | estado terminal, resultado seguro ou código de erro, duração e validações |
| CAD | referências de transação, ordem e resultado: commit, abort, undo ou desconhecido |
| Privacidade | quantidade de remoções aplicadas ao registro |

O registro não contém o token de autenticação da ponte, chave de provedor,
traceback, macro, código arbitrário ou o histórico completo de mensagens.

## Local de armazenamento

Por padrão, `default_audit_store()` usa a pasta de dados do usuário fornecida por
`platformdirs`, sob `ai-cad-workbench/audit`. Esse caminho fica fora do
repositório e é adequado a dados persistentes, ao contrário da pasta efêmera da
ponte ou do cache visual.

`AICAD_AUDIT_DIR` permite escolher explicitamente outro diretório. O override é
útil para testes, diagnóstico e instalações administradas; ele não deve apontar
para a árvore Git.

A estrutura é:

```text
audit/
  v1/
    <session_id>/
      <action_id>.json
```

Uma ação por arquivo permite atualizar seu snapshot por substituição atômica sem
reescrever toda a sessão. Arquivos temporários usam criação exclusiva, `fsync`,
`os.replace` e permissões somente do usuário. Diretórios ou arquivos simbólicos
no caminho controlado são recusados.

## Retenção

A política padrão mantém:

- até 90 dias;
- até 50 sessões;
- até 1.000 ações por sessão.

Os limites são explícitos em `AuditRetentionPolicy`. A limpeza considera somente
diretórios e arquivos com nomes UUID no namespace versionado, nunca segue links
simbólicos e não remove arquivos desconhecidos. Isso mantém a operação limitada
ao armazenamento que pertence ao próprio módulo.

## Redaction

Antes de persistir ou exportar, o módulo percorre todo o payload com limites de
profundidade, quantidade de itens e tamanho de texto. Ele remove:

- valores sob chaves como `api_key`, `password`, `secret`, `credential`,
  `authorization`, `cookie` e qualquer variante de token;
- atribuições sensíveis embutidas em texto;
- credenciais `Bearer`;
- valores secretos conhecidos fornecidos pelo chamador;
- conteúdo binário e tipos secretos do Pydantic;
- caminhos absolutos dentro de pastas pessoais de usuários.

`state_token` e `base_state_token` são contratos de estado do documento, não
credenciais, e permanecem no histórico; tokens de sessão ou autenticação continuam
sempre removidos.

Números não finitos, chaves não textuais, tipos não serializáveis e payloads fora
dos limites falham fechados. A ação não é gravada parcialmente.

## Exportação

`AuditStore.export_session` exige uma sessão e um destino explícitos. O destino:

- precisa estar em um diretório existente e não simbólico;
- não é sobrescrito sem `overwrite=True` explícito;
- recebe uma escrita atômica e permissões restritas;
- passa novamente pelo redaction antes da gravação;
- contém a versão do schema, a sessão, o horário da exportação e os registros.

O exportador é projetado como `cad.export_audit_history`, com risco `export`, no
mesmo registro do chat e MCP. O chat exige um caminho absoluto e confirmação
visual; a aceitação automática de mutações não o autoriza. Depois da execução,
o bundle é regravado para que a própria ação de exportação apareça em estado
terminal no arquivo produzido.

## Integração dos fluxos

- comandos locais guardam o texto original e a intenção determinística;
- leituras e planos da IA guardam o pedido original, entendimento e suposições;
- MCP usa o `request_id` como `action_id`, preservando idempotência;
- planos guardam contrato, estado-base, hash, passos e chamadas congeladas;
- cada executor abre um escopo por `call_id`; compensações usam
  `rollback:<call_id>` e referenciam a transação desfeita;
- `cad.get_audit_history` retorna somente um resumo limitado da sessão atual;
- `cad.export_audit_history` gera um bundle completo e redigido.

## Aceite

A suíte atual cobre contrato, redaction, limites, revisões, retenção, exportação,
aprovação manual/automática, planos e MCP sem FreeCAD. O smoke gráfico cria e
desfaz objetos por chat e MCP, executa plano composto, consulta o histórico e
exporta o bundle no FreeCAD 1.1.1 real, instalado no Windows, verificando commits
e undos relacionados.
