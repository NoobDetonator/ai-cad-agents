# Arquitetura

## Princípios

1. O servidor MCP é o produto principal.
2. O FreeCAD é um adaptador geométrico, não a camada de regras.
3. Chat e MCP chamam o mesmo `ToolRegistry`.
4. Toda mutação é validada, transacional, auditada e reversível.
5. Texto do agente nunca é executado como Python, macro ou shell.

## Componentes

| Camada | Responsabilidade |
| --- | --- |
| `core/tool_catalog` | nomes, schemas, risco, busca, exemplos e schemas de saída |
| `core/tool_registry.py` | validação e despacho único das ferramentas |
| `application.py` | protocolo do adaptador e associação dos handlers |
| `adapters/freecad` | operações geométricas e transações no FreeCAD |
| `bridge` | protocolo autenticado, fila, confirmação e dispatcher da GUI |
| `orchestration` | planos imutáveis, receitas, aprovação e rollback |
| `mcp_server.py` | projeção do catálogo, planos, recursos e prompts pelo MCP |
| `audit` | eventos locais, redaction, retenção e exportação controlada |
| `ui` | painel, estado visível de aprovação e integração Qt |

Dependências apontam para dentro: catálogo e orquestração não importam FreeCAD.
O código importável fora do aplicativo permanece testável com adaptadores falsos.

## Fluxo MCP

```text
agente externo
  → servidor MCP por stdio
  → ponte TCP loopback autenticada
  → dispatcher na thread Qt
  → ToolRegistry
  → adaptador FreeCAD
  → transação, recompute e validação
  → resultado estruturado
```

A GUI cria uma sessão efêmera com host loopback, porta e token fortes. O arquivo
de descoberta fica no runtime local, fora do Git. O cliente MCP aguarda por mais
tempo que o dispatcher da GUI, permitindo operações CAD longas sem falso timeout.

## Risco e aprovação

As ferramentas são classificadas como:

- `read`: leitura imediata;
- `modify`: mutação reversível submetida à política visível do painel;
- `export`: gravação externa sempre confirmada manualmente.

A aceitação automática inicia ligada para mutações, mas pode ser desmarcada.
Ela não remove validação, auditoria, transação ou undo e nunca vale para exportar.

## Contrato de mutação

Uma mutação válida:

1. valida o schema e resolve referências sem ambiguidade;
2. registra o estado-base do documento;
3. abre uma transação nomeada;
4. executa apenas a operação registrada;
5. recalcula e valida forma, documento e pós-condições;
6. confirma a transação ou aborta integralmente.

Features derivadas guardam links para as fontes. Elas são BReps controlados e
reversíveis, mas ainda não formam uma árvore Part Design totalmente paramétrica.

## Planos

Uma mutação pode ser autorizada isoladamente ou em um plano de duas a oito
chamadas. O plano é congelado com hash e estado-base. Mudanças no documento,
argumentos diferentes ou autorização expirada invalidam a execução.

Planos compostos validam cada passo. Se um passo falhar, o executor desfaz os
passos anteriores e confirma que o fingerprint voltou ao estado inicial.

## Contexto e referências

O agente deve ler o contexto antes de editar. O snapshot inclui documento,
seleção, objetos recentes e token de estado. Resolução por nome ou label nunca
escolhe silenciosamente entre candidatos ambíguos.

Operações por aresta usam assinaturas geométricas, não índices topológicos crus.
Sketches expõem índices limitados e devem ser consultados novamente após trim ou
exclusão, pois o Sketcher pode renumerar geometria.

## Geometria e coordenadas

- caixa e placa usam o canto mínimo na origem;
- cilindro e cone usam o eixo central na origem;
- coordenadas de furos são globais;
- `cad.create_through_hole` atravessa toda a altura por padrão;
- `z_min` e `z_max` limitam o furo a uma faixa vertical;
- pads seguem a normal do plano XY, XZ ou YZ do Sketch.

Essas convenções aparecem nas descrições do catálogo e evitam compensações
implícitas no agente.

## Captura visual

`cad.capture_view` grava um PNG sob demanda. `cad.capture_views` produz até oito
vistas independentes em uma chamada; o conjunto padrão é isométrica, frente,
topo e direita. Cada imagem retorna um ID opaco e o recurso
`aicad://view/{capture_id}`.

O cache aceita até 8 MiB por imagem, mantém quantidade limitada de capturas e
fica fora do Git. As capturas desativam animações temporariamente, estabilizam o
viewport, ocultam overlays e restauram o estado visual original mesmo em falha.
A imagem vem do framebuffer visível, evitando diferenças do render off-screen.

## Erros e auditoria

Erros de domínio, como referência inexistente ou raio incompatível, chegam ao
cliente em texto curto para permitir autocorreção. Exceções internas continuam
ocultas. Mensagens passam por redaction e limite de tamanho.

A auditoria registra pedido, plano, risco, aprovação, argumentos validados,
resultado, duração, transações e undo. Segredos e caminhos pessoais são removidos
antes da gravação. Veja [audit.md](audit.md).

## Baseline de testes

- testes unitários sem FreeCAD;
- adaptadores falsos para transação e orquestração;
- smokes no FreeCADCmd para geometria real;
- smoke gráfico para painel, MCP, seleção e captura;
- benchmarks offline para recuperação segura de ferramentas.

O comando obrigatório é `scripts/testar.ps1`.
