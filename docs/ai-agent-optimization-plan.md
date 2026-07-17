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
  → validação, medida e captura multivista
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

O agente não recebe as 92 ferramentas em toda chamada. Um seletor local procura
termos PT/EN, famílias, aliases e tags e envia um conjunto pequeno. Pedidos
inseguros não recuperam mutações.

O fluxo normal usa `search_cad_capabilities` para cartões compactos e
`describe_cad_capabilities` para schemas sob demanda. O catálogo completo
permanece disponível por `available_cad_tools` apenas para compatibilidade e
auditoria. A descrição da ferramenta é o contrato operacional; documentação
narrativa não deve duplicar todos os schemas.

## Contexto eficiente

- começar com `cad.get_context_snapshot`;
- pedir detalhes somente dos objetos relevantes;
- resolver ambiguidades por seleção, nunca por palpite;
- medir antes de alterar quando a geometria existente importa;
- recapturar ou medir depois da operação;
- paginar documentos grandes.

## Autocorreção segura

O dispatcher classifica falhas, informa se o estado foi restaurado e sugere
ações tipadas. Causas de domínio são redigidas; detalhes internos permanecem
genéricos. Transporte interrompido exige nova leitura de contexto. O agente pode
corrigir argumentos e tentar outra ferramenta registrada, mas nunca repetir uma
mutação ambígua nem gerar Python como fuga.

## Planos e latência

Leituras simples executam imediatamente. Mutações podem ser agrupadas em planos
de duas a oito chamadas, reduzindo confirmações sem ampliar a autorização. O
cliente MCP aguarda operações CAD longas por mais tempo que o dispatcher da GUI.

Para inspeção visual, `cad.capture_views` entrega isométrica e vistas ortogonais
em uma chamada e restaura a câmera. Isso reduz viagens MCP e evita que uma vista
dependa do estado deixado pela anterior.

Quando o interior importa, `cad.capture_section_view` aplica temporariamente um
corte XY, XZ ou YZ com offset, captura o framebuffer real e restaura integralmente
o estado visual.

Na fachada MCP, `inspect_cad_model` reúne contexto, validação, medidas e,
opcionalmente, detalhes, dependências e vistas. Uma segunda leitura de contexto
compara o token final ao inicial para detectar edição concorrente.

## Métricas permanentes

### Telemetria ponta a ponta

`get_mcp_performance_snapshot` mantém métricas somente em memória e sem conteúdo
dos argumentos. O snapshot separa:

- chamadas, falhas, bytes de entrada e saída por ferramenta MCP;
- estimativa explícita de tokens por bytes UTF-8 divididos por quatro;
- ida e volta do bridge por operação;
- fila da GUI, espera de confirmação e execução no FreeCAD;
- espera completa de workflows entre submissão e estado terminal.

A estimativa não inclui framing do transporte nem substitui o tokenizer do cliente.
As métricas são descartadas ao encerrar o processo MCP.

A primeira baseline real está versionada em
`benchmarks/mcp-baseline-placa-canonica-v1.json`: a placa canônica do P6
custa 142 chamadas de ponte (~25 s de ponte, ~39 s de execução na GUI),
~66 KiB de payload MCP e ~16,6 mil tokens estimados em 65 mutações. É a
referência de comparação para planos compostos, `get_cad_changes` e CAD-IR.

### Recuperação e generalização

O benchmark agora informa recall, rank-1, MRR, precisão@K, cobertura de
esclarecimentos, filtros de rejeição e falsos positivos de mutação. Os corpora
históricos continuam como regressão curada. O corpus
`agent-corpus-heldout-v1.json` é separado, versionado e rejeita frases iguais a
aliases ou exemplos do catálogo.

Baseline holdout congelada em 36 casos, top-4:

- recall direto: 10/20 (50%);
- rank-1: 42,9%; MRR: 0,440; precisão@K: 17,3%;
- cobertura de esclarecimentos: 3/8 (37,5%);
- exposição de mutação em rejeições: 1/8;
- economia teórica sem cache: 97,4%.

Esses números são intencionalmente mais baixos que os corpora curados e não são
usados para ajustar os pesos. A economia de schemas assume que o catálogo
completo seria reenviado; clientes que armazenam `tools/list` em cache têm ganho
real menor.

## Direção atual

Novas ferramentas entram apenas quando cobrem tarefas reais. Cada incremento
deve trazer schema pequeno, descrição precisa, teste sem FreeCAD quando possível,
smoke geométrico quando necessário e evidência visual em projetos de teste.

A IA embutida permanece em manutenção. A escolha de provedor é responsabilidade
do agente externo conectado ao MCP.
