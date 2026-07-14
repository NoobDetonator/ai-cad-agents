# AI CAD Workbench

Servidor MCP seguro que dá a agentes de IA — Claude Code, Codex, Cursor e
qualquer cliente MCP — ferramentas estruturadas, validadas e reversíveis para
modelar peças reais no FreeCAD. O FreeCAD é o motor CAD; contratos, política de
risco, receitas e orquestração permanecem independentes dele.

Diferente dos MCPs de CAD que executam Python arbitrário dentro do aplicativo,
aqui não existe caminho para executar código gerado: o agente chama ferramentas
pequenas com schema, cada mutação é transacional, confirmada visualmente pelo
usuário, auditada e reversível.

O produto principal é o MCP; a IA vem do agente que o usuário já usa. O painel
dentro do FreeCAD funciona como superfície de confirmação e inclui um modo de
chat local e um modo DeepSeek standalone opcional, ambos em manutenção.

## Estado atual

Os marcos M0 a M5 estão implementados. O corte funcional atual oferece:

- Workbench **AI CAD** e painel lateral testados no FreeCAD 1.1.1;
- um único `ToolRegistry`, com 30 ferramentas, usado pelo chat e pelo MCP;
- chat local determinístico e modo DeepSeek opcional;
- leituras de documento, seleção, contexto, objetos, medidas, dependências,
  parâmetros editáveis e imagem da vista;
- criação e edição de primitivas, placas, furos, padrões, sketch retangular, pad,
  booleanas, filetes e chanfros;
- três receitas confiáveis: placa de fixação, flange e pad retangular;
- planos de uma ou várias mutações com confirmação visual, validação e rollback;
- MCP com ferramentas, receitas, prompts e recursos derivados dos mesmos serviços;
- nenhum caminho para executar Python, macro, shell ou texto gerado como código.

O M5 registra pedidos, entendimento da IA, planos, argumentos validados, risco,
aprovação, resultado, duração, validações e transações reais do FreeCAD. O
histórico local versionado aplica redaction antes de gravar, fica fora do Git e
pode ser consultado ou exportado com confirmação pelo mesmo registro do chat e MCP.

As features derivadas por furo, padrão, pad, booleana, filete e chanfro guardam
links para os objetos de origem e são reversíveis. Nesta fase elas são resultados
BRep controlados, não uma árvore Part Design totalmente paramétrica que se atualiza
automaticamente após toda mudança na origem.

## Preparação e abertura

Em uma máquina ainda não preparada:

```powershell
.\scripts\setup.ps1
```

Se o ambiente já existe, não execute o setup novamente e não baixe o FreeCAD.
Abra o projeto com:

```powershell
.\scripts\iniciar.ps1
```

O Workbench **AI CAD** aparecerá na lista e abrirá o painel à direita.

Para desenvolvimento repetitivo, abra pelo lançador rápido:

```powershell
.\scripts\iniciar_rapido.ps1
```

Nesse lançador, **Modo de teste rápido** começa marcado e confirma automaticamente
mutações locais, da IA e do MCP. O estado fica visível no painel e pode ser
desmarcado a qualquer momento. O modo vale somente para a sessão; schemas,
transações, validação, pós-condições e undo continuam obrigatórios. O lançador
normal permanece com confirmação visual.

## Chat local

O modo local não usa provedor. Exemplos:

```text
resumo
seleção
contexto
detalhes Base
medir Base
dependências Base
parâmetros Base
validar
caixa 10 x 20 x 30 nome Corpo
cilindro 30 x 60 nome Eixo
placa 100 x 60 x 8 nome Base
desfazer
```

Leituras são imediatas. Mutações mostram o plano e exigem **Confirmar operação**.
Texto desconhecido recebe ajuda; nunca é avaliado como código.

## IA DeepSeek

O modo DeepSeek fica desligado até o usuário marcá-lo. A chave só é necessária
para uma chamada real e é armazenada pelo `keyring` no Gerenciador de Credenciais
do Windows, nunca em `.env`, arquivos do projeto, logs ou histórico.

Antes de chamar o modelo, um seletor local PT/EN envia no máximo quatro ferramentas
relevantes. O agente pode executar leituras limitadas e replanejar, mas qualquer
mutação encerra a descoberta em `awaiting_approval`. Se a instrução depender de
um único objeto e a seleção não for inequívoca, o turno para em
`awaiting_selection` e pede uma seleção no FreeCAD sem alterar o documento.

Planos aprovados são congelados com hash e estado-base. A autorização vale apenas
para as chamadas exibidas e expira rapidamente. O executor relê o documento,
revalida os schemas e verifica a pós-condição. Planos de duas a oito operações
possuem aprovação única e rollback compensatório verificado.

## Ferramentas do Marco 4

Leituras:

- `cad.get_object_details`, `cad.measure_object`, `cad.get_dependencies`;
- `cad.resolve_object`, `cad.get_editable_parameters`, `cad.capture_view`.

Mutações:

- `cad.rename_object`, `cad.set_parameter`, `cad.transform_object`;
- `cad.create_plate`, `cad.create_through_hole`;
- `cad.create_rectangular_hole_pattern`, `cad.create_circular_hole_pattern`;
- `cad.create_rectangular_sketch`, `cad.pad_sketch`;
- `cad.boolean_operation`, `cad.fillet_edges`, `cad.chamfer_edges`.
- `cad.create_spur_gear`, baseada no gerador involuto oficial do FreeCAD.

Exportações (M6, risco `export`, confirmação sempre manual):

- `cad.export_stl` e `cad.export_step` exportam um objeto sólido validado para
  um destino absoluto explícito, sem sobrescrita silenciosa, e devolvem
  tamanho e SHA-256 do artefato para verificação.

Todas têm schemas pequenos e são validadas pelo registro. Mutações usam a mesma
rotina transacional: abrem uma transação nomeada, recalculam, validam forma e
documento, confirmam no sucesso e abortam na falha. Operações por aresta recebem
assinaturas geométricas estáveis no contrato, não índices topológicos expostos.

## Receitas e MCP

O `RecipeCatalog` compila parâmetros tipados somente para chamadas registradas:

- `mounting_plate`: placa e padrão retangular de furos;
- `flange`: cilindro e padrão circular de furos;
- `rectangular_pad`: sketch retangular e pad.

O MCP publica o catálogo com `available_cad_tools` e `available_cad_recipes`.
`submit_cad_recipe` cria um plano revisável; `submit_cad_plan`,
`get_cad_plan_status` e `cancel_cad_plan` controlam planos compostos. A execução
continua na GUI do FreeCAD e exige confirmação visual.

Também são publicados:

- recurso `aicad://recipes`;
- recurso PNG `aicad://view/{capture_id}`;
- prompts `model_mounting_plate`, `model_flange` e `model_rectangular_pad`.

Capturas são feitas somente sob demanda, limitadas a PNG de 8 MiB, guardadas no
cache local do usuário e identificadas por ID opaco. Caminhos locais não chegam
ao modelo nem entram no Git.

## Testes e benchmark

Execute antes de concluir qualquer alteração:

```powershell
.\scripts\testar.ps1
```

A suíte cobre código neutro, transações reais em FreeCADCmd, todas as operações
mecânicas e um smoke gráfico que abre o Workbench, inspeciona o painel, exercita
MCP, seleção e captura visual. Os marcadores esperados são:

```text
FREECAD_SMOKE_OK
FREECAD_M4_SMOKE_OK
FREECAD_M6_SMOKE_OK
FREECAD_GUI_SMOKE_OK
```

O benchmark offline não usa rede, chave ou FreeCAD:

```powershell
.\scripts\benchmark_agent.ps1 -Strategy selector
```

No corpus mecânico M4, o seletor recupera 30/30 ferramentas esperadas. No corpus
geral, envia um subconjunto pequeno das 30 ferramentas e economiza 91,8% dos bytes de
schemas.

## Segurança

- Chat e MCP passam pelo mesmo `ToolRegistry` e pelo mesmo adaptador.
- O MCP usa TCP loopback autenticado e transfere execução para a thread Qt.
- Toda mutação de IA ou MCP exige confirmação explícita.
- A única exceção é o modo de desenvolvimento iniciado explicitamente por
  `iniciar_rapido.ps1`; ele emite aprovações automáticas somente naquela sessão.
- Não existe ferramenta de Python arbitrário, macro ou shell.
- Chaves permanecem no cofre do Windows.
- `.runtime`, `.tools`, `.downloads`, `.venv`, capturas, CAD gerado e segredos
  permanecem fora do Git.

## Conectar um agente externo

O repositório traz um `.mcp.json` pronto: abrindo o Claude Code nesta pasta,
o servidor `ai-cad` é oferecido automaticamente. Com o FreeCAD aberto por
`.\scripts\iniciar.ps1`, o agente lê o documento, propõe planos que você
confirma no painel e exporta STL/STEP. O passo a passo para Claude Code,
Codex e Cursor está em [docs/mcp-integration.md](docs/mcp-integration.md).

## Documentação

- [Integração MCP com agentes externos](docs/mcp-integration.md)
- [Arquitetura](docs/architecture.md)
- [Visão do produto](docs/product-vision.md)
- [Marcos e transferência](docs/milestones.md)
- [Plano de otimização do agente](docs/ai-agent-optimization-plan.md)
- [Contrato e armazenamento de auditoria](docs/audit.md)

## Roteiro

Estratégia vigente: **MCP primeiro** (decisão de 14/07/2026, detalhada em
`docs/milestones.md` e `docs/product-vision.md`).

- **M6 — MCP como produto**: exportação STL/STEP controlada, guia de
  integração testado com Claude Code/Codex/Cursor e feedback visual para o
  agente. Fecha o fluxo "pedido em linguagem natural → arquivo fabricável".
- **M7 — Cobertura de modelagem**: sketch constrangido, revolução, sweep,
  loft, furos com rebaixo e novas receitas.
- **M8 — Lançamento público**: instalação simples, docs de usuário, demo
  gravada e abertura do repositório.

A IA embutida (modo DeepSeek, seletor e loop) está em modo manutenção: segue
funcionando e testada, mas as horas novas vão para o MCP. Não haverá suporte
multi-provedor interno — o usuário escolhe o modelo ao escolher o agente.
