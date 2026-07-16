# Otimização do agente

Este plano foi executado entre M3 e M7. O foco atual é manter os contratos e
medir incrementos novos, não reabrir a arquitetura concluída.

## Objetivo

Permitir que um agente externo encontre poucas ferramentas relevantes, leia o
estado real do documento, proponha operações verificáveis e se corrija usando
erros, medidas e capturas, sem receber acesso a código arbitrário.

## Pipeline atual

```text
pedido
  → seleção PT/EN de poucas ferramentas
  → contexto versionado
  → leituras limitadas
  → plano imutável
  → aprovação visível
  → execução transacional
  → validação, medida e captura
```

## Contratos entregues

- metadados de ferramenta: nome, família, risco, aliases, tags e exemplos;
- `DocumentStateToken`: documento e fingerprint usados como estado-base;
- contexto paginado com seleção, objetos e referências recentes;
- plano validado e congelado;
- autorização limitada às chamadas exibidas;
- resultados estruturados e erros de domínio curtos;
- planos compostos com rollback compensatório verificado;
- receitas tipadas compiladas apenas para ferramentas registradas.

## Estratégia de seleção

O agente não recebe as 90 ferramentas em toda chamada. Um seletor local procura
termos PT/EN, famílias, aliases e tags e envia um conjunto pequeno. Pedidos
inseguros não recuperam mutações.

O catálogo completo permanece disponível por `available_cad_tools`. A descrição
da ferramenta é o contrato operacional; documentação narrativa não deve duplicar
todos os schemas.

## Contexto eficiente

- começar com `cad.get_context_snapshot`;
- pedir detalhes somente dos objetos relevantes;
- resolver ambiguidades por seleção, nunca por palpite;
- medir antes de alterar quando a geometria existente importa;
- recapturar ou medir depois da operação;
- paginar documentos grandes.

## Autocorreção segura

O dispatcher expõe `ValueError`, `RuntimeError` e referências ausentes em texto
redigido e limitado. Erros internos permanecem genéricos. O agente pode ajustar
argumentos e tentar outra ferramenta registrada, mas não gerar Python como fuga.

## Planos e latência

Leituras simples executam imediatamente. Mutações podem ser agrupadas em planos
de duas a oito chamadas, reduzindo confirmações sem ampliar a autorização. O
cliente MCP aguarda operações CAD longas por mais tempo que o dispatcher da GUI.

## Métricas permanentes

- ferramenta esperada presente no conjunto recuperado;
- tamanho total dos schemas enviados;
- mutações ausentes em pedidos inseguros;
- número de leituras antes do plano;
- sucesso geométrico e validade do documento;
- tempo até resultado confirmado;
- rollback correto após falha induzida.

Os corpora em `benchmarks/` cobrem modelagem geral, fundamentos, rolamentos e
Sketch. O benchmark é offline e não usa chaves nem FreeCAD.

## Direção atual

Novas ferramentas entram apenas quando cobrem tarefas reais. Cada incremento
deve trazer schema pequeno, descrição precisa, teste sem FreeCAD quando possível,
smoke geométrico quando necessário e evidência visual em projetos de teste.

A IA embutida permanece em manutenção. A escolha de provedor é responsabilidade
do agente externo conectado ao MCP.
