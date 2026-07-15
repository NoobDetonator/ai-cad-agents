# AI CAD Workbench

Servidor MCP seguro que dá a agentes de IA — Claude Code, Codex, Cursor e
qualquer cliente MCP — ferramentas estruturadas, validadas e reversíveis para
modelar peças reais no FreeCAD. O FreeCAD é o motor CAD; contratos, política de
risco, receitas e orquestração permanecem independentes dele.

Diferente dos MCPs de CAD que executam Python arbitrário dentro do aplicativo,
aqui não existe caminho para executar código gerado: o agente chama ferramentas
pequenas com schema; cada mutação passa pela política visível do painel, é
transacional, auditada e reversível. A aceitação automática inicia ligada, pode
ser desmarcada a qualquer momento e nunca se aplica a exportações.

O produto principal é o MCP; a IA vem do agente que o usuário já usa. O painel
dentro do FreeCAD funciona como superfície de confirmação e inclui um modo de
chat local e um modo DeepSeek standalone opcional, ambos em manutenção.

## Estado atual

Os marcos M0 a M7 estão implementados. O corte funcional atual oferece:

- Workbench **AI CAD** e painel lateral testados no FreeCAD 1.1.1;
- um único `ToolRegistry`, com 90 ferramentas, usado pelo chat e pelo MCP;
- chat local determinístico e modo DeepSeek opcional;
- leituras de documento, seleção, contexto, objetos, medidas, dependências,
  parâmetros editáveis e imagem da vista;
- criação de caixa, cilindro, cone, esfera e toro; medição de distância mínima;
- duplicação e exclusão segura, transformação absoluta e deslocamento/rotação relativos;
- criação e edição de placas, furos, padrões, furos com rebaixo,
  escareado e roscados, sketch retangular e circular constrangidos, pad,
  booleanas, filetes e chanfros;
- ambiente paramétrico de Sketch com 24 ferramentas dedicadas: planos XY/XZ/YZ,
  linhas, polilinhas, arcos, círculos, elipses, retângulos, rasgos e polígonos;
  geometria externa, construção, cotas, restrições geométricas, inspeção do
  solver, mover, copiar, espelhar, aparar, estender, filetar e excluir;
- trajetórias linha/arco e varredura de perfil (sweep) ao longo delas;
- engrenagens retas e helicoidais com fase de dentes para engrenamento,
  roscas externas e internas;
- engrenagem interna involuta, porta-planetas, rolamento de esferas, backlash
  geométrico, alinhamento concêntrico e análise de interferências;
- rolamentos rígido de esferas com pistas profundas, axial de esferas e de
  rolos cilíndricos, além de rolamento print-in-place e bucha polimérica
  preparados para folgas de fabricação aditiva;
- espelhamento e padrões linear e polar de features;
- cinco receitas confiáveis: placa de fixação, flange, pad retangular, eixo
  escalonado e polia plana;
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

## Instalação e abertura

O fluxo normal usa o **FreeCAD 1.1.1 instalado no Windows**. Neste computador ele
está em `C:\Program Files\FreeCAD 1.1`; não é necessário baixar outra cópia nem
usar um script para abrir o aplicativo.

Uma única vinculação coloca `src\freecad\AiCad` em
`%APPDATA%\FreeCAD\v1-1\Mod\AiCad`. O Workbench descobre automaticamente a raiz do
checkout e usa `src` e a `.venv` do projeto. O procedimento completo está em
[docs/installation.md](docs/installation.md).

Depois da vinculação, abra o FreeCAD normalmente pelo menu Iniciar e selecione o
Workbench **AI CAD**. O painel abrirá à direita e publicará a ponte MCP.

Os scripts `setup.ps1` e `iniciar.ps1` permanecem somente como auxiliares para o
ambiente portátil de desenvolvimento. O modo explícito de desenvolvimento ainda
existe:

```powershell
.\scripts\iniciar_rapido.ps1
```

O painel agora inicia com **Aceitar automaticamente as alterações** marcado tanto
na abertura normal quanto nesse lançador. Mutações locais, da IA e do MCP passam
pela mesma fila e recebem uma aprovação automática auditada. A opção pode ser
desmarcada a qualquer momento; schemas, transações, validação, pós-condições e
undo continuam obrigatórios. Exportações permanecem sempre manuais. Defina
`AICAD_QUICK_TEST_MODE=0` para iniciar uma sessão em confirmação manual.

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

Leituras são imediatas. Mutações mostram o plano e, com a opção padrão marcada,
são aceitas automaticamente; desmarque-a para exigir **Confirmar operação**.
Texto desconhecido recebe ajuda e nunca é avaliado como código.

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

Documentos e modelagem avançada (M7):

- `cad.list_documents`, `cad.new_document`, `cad.set_active_document` e
  `cad.save_document` organizam peças em documentos separados; salvar exige
  destino `.FCStd` explícito no primeiro salvamento;
- `cad.create_circular_sketch`, `cad.revolve_sketch` e `cad.loft_sketches`
  cobrem peças torneadas e transições entre perfis;
- `cad.create_counterbore_hole`, `cad.create_countersunk_hole` e
  `cad.create_threaded_hole` abrem furos com rebaixo cilíndrico (parafuso
  allen), escareado cônico (cabeça chata) e rosca interna ISO 60°;
- `cad.create_sweep_path` cria trajetórias abertas de linhas e arcos e
  `cad.sweep_sketch` varre um perfil fechado ao longo delas (tubos, dutos);
- `cad.mirror_object`, `cad.linear_pattern` e `cad.polar_pattern` espelham e
  repetem sólidos por plano, eixo linear e círculo;
- `cad.create_rectangular_sketch` e `cad.create_circular_sketch` agora geram
  sketches totalmente constrangidos;
- `cad.create_helical_gear` gera engrenagem helicoidal com o perfil involuto
  oficial e torção controlada; as engrenagens aceitam `phase` para alinhar o
  engrenamento sem transform manual;
- `cad.create_external_thread` gera rosca externa estilo ISO 60° para
  impressão 3D.

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
- `rectangular_pad`: sketch retangular e pad;
- `stepped_shaft`: dois cilindros coaxiais empilhados e fundidos num eixo;
- `flat_pulley`: corpo e duas flanges fundidos, com furo de eixo.

O MCP publica o catálogo com `available_cad_tools` e `available_cad_recipes`.
`submit_cad_recipe` cria um plano revisável; `submit_cad_plan`,
`get_cad_plan_status` e `cancel_cad_plan` controlam planos compostos. A execução
continua na GUI do FreeCAD e exige confirmação visual.

Também são publicados:

- recurso `aicad://recipes`;
- recurso PNG `aicad://view/{capture_id}`;
- prompts `model_mounting_plate`, `model_flange`, `model_rectangular_pad`,
  `model_stepped_shaft` e `model_flat_pulley`.

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
FREECAD_FOUNDATION_SMOKE_OK
FREECAD_SKETCH_SMOKE_OK
FREECAD_ASSEMBLY_SMOKE_OK
FREECAD_BEARINGS_SMOKE_OK
FREECAD_M4_SMOKE_OK
FREECAD_M6_SMOKE_OK
FREECAD_M7_SMOKE_OK
FREECAD_GUI_SMOKE_OK
```

O benchmark offline não usa rede, chave ou FreeCAD:

```powershell
.\scripts\benchmark_agent.ps1 -Strategy selector
```

No corpus mecânico M4, o seletor recupera 46/46 ferramentas esperadas. No corpus
geral, envia um subconjunto pequeno das 90 ferramentas. No corpus fundamental,
recupera 16/16 ferramentas, não expõe mutações nos quatro pedidos inseguros e
economiza 94,8% dos bytes de schemas. O corpus especializado distingue 10/10
pedidos PT/EN de rolamentos e bloqueia os três pedidos inseguros. O corpus de
Sketch recupera 24/24 capacidades e bloqueia quatro tentativas inseguras.

## Segurança

- Chat e MCP passam pelo mesmo `ToolRegistry` e pelo mesmo adaptador.
- O MCP usa TCP loopback autenticado e transfere execução para a thread Qt.
- Toda mutação de IA ou MCP passa pela política de aprovação visível no painel.
- A aceitação automática inicia ligada e emite uma aprovação auditada para cada
  operação exata; pode ser desmarcada para restaurar cliques manuais. Exportações
  não recebem aprovação automática.
- Não existe ferramenta de Python arbitrário, macro ou shell.
- Chaves permanecem no cofre do Windows.
- `.runtime`, `.tools`, `.downloads`, `.venv`, capturas, CAD gerado e segredos
  permanecem fora do Git.

## Conectar um agente externo

O repositório traz um `.mcp.json` pronto: abrindo o Claude Code nesta pasta,
o servidor `ai-cad` é oferecido automaticamente. Com o FreeCAD instalado aberto
normalmente e o Workbench **AI CAD** ativo, o agente lê o documento, propõe planos
que o painel autoriza conforme a opção visível e exporta STL/STEP somente após
confirmação manual. O passo a passo para Claude Code,
Codex e Cursor está em [docs/mcp-integration.md](docs/mcp-integration.md).

## Documentação

- [Instalação com o FreeCAD do Windows](docs/installation.md)
- [Integração MCP com agentes externos](docs/mcp-integration.md)
- [Arquitetura](docs/architecture.md)
- [Ambiente paramétrico de Sketch](docs/sketch-environment.md)
- [Rolamentos convencionais e para impressão 3D](docs/bearings.md)
- [Visão do produto](docs/product-vision.md)
- [Marcos e transferência](docs/milestones.md)
- [Plano de otimização do agente](docs/ai-agent-optimization-plan.md)
- [Contrato e armazenamento de auditoria](docs/audit.md)

## Estado dos marcos

Estratégia vigente: **MCP primeiro** (decisão de 14/07/2026, detalhada em
`docs/milestones.md` e `docs/product-vision.md`).

- **M6 — MCP como produto** (concluído): exportação STL/STEP controlada, guia
  de integração testado com Claude Code/Codex/Cursor e o fluxo "pedido em
  linguagem natural → arquivo fabricável" exercitado de ponta a ponta.
- **M7 — Cobertura de modelagem** (concluído): documentos, revolução, loft,
  sweep, sketch constrangido, furos com rebaixo/escareado/roscados,
  engrenagens com fase, rosca interna, espelhamento, padrões e novas receitas.

M0 a M7 formam a baseline concluída. Não existe um próximo marco pré-definido;
correções e incrementos novos devem partir de uma necessidade
concreta, preservar a arquitetura segura e atualizar testes e documentação.

A IA embutida (modo DeepSeek, seletor e loop) está em modo manutenção: segue
funcionando e testada, mas as horas novas vão para o MCP. Não haverá suporte
multi-provedor interno — o usuário escolhe o modelo ao escolher o agente.
