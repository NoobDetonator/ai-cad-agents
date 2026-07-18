# TALOS — P: Claude profissional em Part Design

## Contexto e posicionamento

O concorrente mais popular ([estudo completo](estudo-freecad-mcp.md)) entrega
amplitude total do FreeCAD com ~2.500 linhas usando reflexão sem allowlist e
Python arbitrário — e nenhuma governança: sem token, sem confirmação, sem
transação, sem auditoria. O TALOS tem a governança e não tem a amplitude.

Este plano busca o melhor dos dois mundos: **capturar o mecanismo de amplitude
dele (reflexão) sob as garantias do TALOS (allowlist, validação, transação,
confirmação, auditoria)**, focado no que faz um modelo ser profissional e
utilizável: árvore Part Design paramétrica, sketches totalmente restritos,
dimensões dirigidas por parâmetros nomeados e validação de engenharia.

O plano P substitui a ordem de implementação do
[E1](mcp-scale-roadmap.md) para trabalho de capacidade. As frentes E1 já
entregues (descoberta, erros recuperáveis, captura, inspetor) permanecem; as
pendentes (pacotes FEM/CAM/BIM, modos visuais restantes, busca semântica,
tarefas MCP) ficam adiadas até o P concluir.

## O que "profissional" significa (critérios de qualidade do modelo)

1. Árvore `PartDesign::Body` editável, não sólidos estáticos booleanos;
2. todo sketch totalmente restrito (0 graus de liberdade);
3. dimensões dirigidas por parâmetros nomeados — mudar `espessura_parede`
   recalcula o modelo inteiro válido;
4. árvore legível: nomes descritivos, features na ordem certa, dressups por
   último;
5. massa, volume e interferência verificados; perfil de fabricação checado;
6. o arquivo `.FCStd` abre no FreeCAD e um humano continua o trabalho por cota.

Hoje o TALOS falha no critério 1 (o `cad.pad_sketch` extruda um sólido
estático via `Part::Feature`, ignora furos internos do wire e não segue o
sketch) e não tem ferramentas para os critérios 2 e 3.

## Princípios (mudanças em relação à baseline)

- **Mantido**: nenhuma execução de Python, macro ou shell arbitrário. A
  amplitude vem de reflexão governada, nunca de `exec`.
- **Mantido**: toda mutação transacional, validada, auditada e reversível;
  confirmação visível; exportação manual.
- **Novo**: onde um registro declarativo de propriedades basta, preferir a
  camada genérica tipada a escrever uma ferramenta à mão. Ferramentas manuais
  ficam para operações com validação geométrica própria.
- **Novo**: toda descrição de ferramenta nova inclui um exemplo JSON completo
  de chamada (padrão aprendido do concorrente — o exemplo ensina mais que a
  prosa).

## A aposta arquitetural: reflexão governada

Núcleo novo no adaptador, inspirado no `property_mapper.py` dele, porém
fechado:

```text
FeatureRegistry (declarativo, por tipo whitelisted)
  tipo FreeCAD          → "PartDesign::Pad"
  propriedades          → {Length: quantidade mm > 0, Reversed: bool, ...}
  alvo obrigatório      → sketch do Body ativo
  pré-condições         → sketch fechado, Body existe
  pós-condições         → recompute válido, shape sólido
  compensável           → sim
```

- Um `cad.create_feature(feature_type, target, properties)` e um
  `cad.edit_feature(feature, properties)` genéricos validam contra o registro:
  tipo fora da allowlist → rejeitado; propriedade fora da allowlist →
  rejeitado; valor fora do domínio → erro estruturado com faixa permitida.
- O mapeador JSON→FreeCAD (Placement, Vector, referência por nome, quantidade
  com unidade) vira módulo neutro testável sem FreeCAD.
- O custo marginal de cobrir uma feature nova cai de "schema manual + handler
  + catálogo + testes dedicados" para **uma linha de registro + teste de
  contrato gerado**.
- `search_cad_capabilities` expõe cada tipo registrado como cartão próprio —
  a fachada MCP não cresce.

## Fases

### P0 — Estudo aplicado ✅

Clone em `.study/` (gitignored), análise registrada em
[estudo-freecad-mcp.md](estudo-freecad-mcp.md), decisões deste plano.

### P1 — Núcleo Part Design paramétrico ✅ (núcleo entregue)

O coração do plano. Estado:

- ✅ **Body**: `cad.create_body`; a árvore aparece no contexto existente;
- ✅ **sketch no Body**: `cad.create_body_sketch` anexa aos planos de origem
  XY/XZ/YZ com offset; as 24 ferramentas de sketch existentes operam nesses
  sketches (anexo a face planar e datum plane dependem do P2);
- ✅ **features via reflexão governada**: Pad, Pocket (com through_all),
  Revolution, Groove, LinearPattern, PolarPattern e Mirrored geradas do
  registro declarativo em `core/partdesign_registry.py`;
- ✅ **edição por cota**: `cad.set_sketch_datum` e `cad.edit_feature` com
  allowlist por tipo;
- ✅ **`cad.get_sketch_status`**: FullyConstrained, DoF, conflitos,
  redundâncias e geometria sub-restrita;
- ✅ depreciação de `cad.pad_sketch`/`cad.revolve_sketch` (mantidos, descrição
  aponta o fluxo paramétrico);
- ✅ smoke real `tests/freecad_partdesign_smoke.py`: body → sketch anexado →
  DoF → pad → pocket through-all → edição por cota (volume determinístico) →
  padrão linear → espelho → revolução → guardas → undo;
- pendente (vai para P2, exige referências de aresta/face): Hole com
  counterbore/countersink, Fillet, Chamfer e Draft como dressups.

### P2 — Referências semânticas estáveis (mínimo do antigo E1.3) ✅ (núcleo entregue)

- ✅ seletores neutros em `core/semantic_refs.py`: face por papel
  (`largest_planar_face` com filtro de normal, `named_face`) e arestas
  (`circular_edges` por diâmetro, `face_boundary`, `named_edges`) —
  resolvidos na execução sobre o tip do Body; referência obsoleta ou ambígua
  falha com erro estruturado, nunca escolhe outra topologia em silêncio;
- ✅ `cad.resolve_body_reference` (leitura): preview da resolução antes de
  mutar;
- ✅ `cad.create_face_sketch`: sketch anexado a face sólida resolvida
  semanticamente — encadeia features sobre geometria existente;
- ✅ `cad.add_fillet` e `cad.add_chamfer`: dressups `PartDesign::` com
  arestas semânticas e volumes verificados no smoke;
- ✅ `cad.add_hole`: furos paramétricos em todos os círculos do sketch, com
  counterbore/countersink, passante e reedição por diâmetro — uma linha no
  registro de reflexão governada;
- pendente: `$ref` entre passos de plano composto (próximo incremento);
- nota empírica: `Face.normalAt` já devolve a normal orientada para fora;
  não aplicar correção por `Orientation`.

### P3 — Parâmetros mestres ✅ (núcleo entregue)

- ✅ `cad.create_parameter_set` (App::VarSet), `cad.set_master_parameter`
  (length/angle/count/factor) e `cad.list_master_parameters`;
- ✅ `cad.rename_sketch_constraint` para dar nome estável às cotas;
- ✅ `cad.bind_sketch_datum` e `cad.bind_feature_parameter` com expressões
  validadas por gramática fechada em `core/expressions.py` (identificadores
  pontuados + aritmética; chamadas de função rejeitadas; null desfaz o
  vínculo);
- ✅ critério 3 provado no smoke: mudar um parâmetro recalcula sketch e
  features com volume exato;
- correção estrutural no caminho: `cad.add_sketch_rectangle` agora cria as
  restrições que a GUI cria (coincidentes nos cantos, horizontal/vertical
  quando não rotacionado) — sem elas, dirigir uma cota rasgava o wire.

### Decisão registrada — `$ref` entre passos de plano

Adiado deliberadamente: como toda criação no TALOS exige nome explícito e
único (`_ensure_new_name`), os passos de um plano já se referenciam de forma
determinística pelos nomes que o próprio plano define. `$ref` volta ao escopo
junto com o CAD-IR completo (E1.3), se a prática mostrar necessidade.

### P4 — Metodologia embutida ✅

- ✅ prompt MCP `part_design_methodology`: os dez passos do fluxo
  profissional, dos parâmetros mestres ao teste final de mudar um parâmetro
  e recalcular válido, citando as ferramentas exatas de cada fase;
- ✅ exemplos JSON completos em toda descrição de ferramenta nova (padrão
  aplicado desde o P1);
- ✅ guia como recurso MCP (`aicad://guides/partdesign`), carregado sob
  demanda, fora do payload normal.

### P5 — Biblioteca de partes e validação de engenharia (validação entregue)

- ✅ `cad.measure_mass_properties`: massa, volume e centro de gravidade
  ponderado por volume a partir de densidade explícita em g/cm³;
- ✅ `cad.analyze_print_readiness`: sólidos fechados, contato com a mesa,
  sólidos flutuantes e faces em balanço além do limite imprimível (+Z,
  normais amostradas no centro da face); espessura mínima de parede
  permanece pendente por exigir análise de offset;
- adiado: `cad.list_library_parts` / `cad.insert_library_part` — o addon
  parts_library não está instalado neste ambiente; quando entrar, o caminho
  será validado (sem path traversal, ao contrário do concorrente);
- FEM permanece adiado; a cadeia guiada do concorrente vira receita futura.

### P6 — Prova ponta a ponta (primeiro canônico entregue)

- ✅ **Placa de montagem paramétrica** dirigida inteiramente via MCP em uma
  sessão (65 mutações, 12 leituras): VarSet com sete parâmetros, sketch base
  ancorado na origem com 0 DoF, furos com counterbore em sketch anexado à
  face superior com centros dirigidos por expressões
  (`Params.comprimento - Params.margem`), chanfro semântico, e duas mudanças
  de parâmetro recalculando a árvore inteira com volume exato. Massa e
  prontidão de impressão verificadas pelas ferramentas do P5. Baseline de
  telemetria versionada em `benchmarks/mcp-baseline-placa-canonica-v1.json`;
- ✅ **Flange paramétrica** (47 mutações, 11 leituras): disco, cubo e furo
  central concêntricos na origem, círculo de parafusos com centro apoiado no
  eixo X, seis furos por `PartDesign::PolarPattern` com `occurrences`
  vinculado a um parâmetro de contagem — `n_furos` 6→8 recontou o padrão com
  volume exato, e `espessura_flange` 10→12 recalculou disco, cubo e furos.
  Baseline em `benchmarks/mcp-baseline-flange-canonica-v1.json`;
- desbloqueios no caminho: restrições aceitam os datums do Sketcher como
  segunda geometria (`-1` = eixo X, cujo ponto inicial é a origem; `-2` =
  eixo Y; geometria externa continua fora do contrato) — sem isso, 0 DoF era
  inalcançável pelo contrato publicado. A convenção real do Sketcher
  (`-1`/`-2` são os eixos, `-3` em diante é geometria externa) está provada
  por sonda de posição no smoke;
- ✅ **Suporte em L** (76 mutações, 13 leituras): parede vertical em sketch
  no plano XZ (o pad de plano vertical sai para −y; `reversed` traz para
  dentro), furos da base e **furos em sketch anexado à face vertical** — o
  frame local da face +y espelha o eixo X, e as cotas entre pontos escolhem
  a ordem que mantém o valor positivo, então as expressões ficam idênticas
  às da base. `parede_altura` e `espessura` recalculam com volume exato.
  Baseline em `benchmarks/mcp-baseline-suporte-canonico-v1.json`;
- nota de heurística: `cad.analyze_print_readiness` não flagra o teto de
  furos horizontais (normal amostrada no centro da face cilíndrica aponta
  para o lado) — limitação declarada em `normals_sampled_at_face_center`;
- ✅ **Case com tampa** (68 mutações, 17 leituras): dois Bodies dirigidos
  pela mesma VarSet — caixa com cavidade e tampa com plugue, folga de
  encaixe como parâmetro (`Params.parede + Params.folga`). A tampa é
  modelada em pose de impressão, posicionada no encaixe por
  `cad.transform_object`, e `cad.analyze_interferences` prova o ajuste:
  contato com volume comum zero quando alinhada, `interference_count: 1`
  quando desalinhada 2 mm de propósito, e `parede` 2,4→3 recalcula os dois
  corpos mantendo o encaixe. Baseline em
  `benchmarks/mcp-baseline-case-canonico-v1.json`;
- pendente: estágio planetário como Bodies paramétricos;
- benchmark com agente real (não seletor lexical): mesmas tarefas no TALOS e
  no freecad-mcp clonado, medindo turnos, tokens, taxa de sucesso e os seis
  critérios de qualidade;
- métrica de regressão: 100% dos sketches canônicos com 0 DoF; mudança de
  parâmetro recalcula válido em 100% dos canônicos; rollback restaura
  fingerprint; zero mutação sem aprovação.

## Ordem e dependências

```text
P1 (Body + features + cota)  ← núcleo, começa já
  P2 (referências)           ← desbloqueia sketch-em-face e dressups robustos
  P3 (parâmetros)            ← profissionaliza; depende só de P1
P4 (metodologia)             ← paralelo, barato, começa com P1
P5 (biblioteca + validação)  ← oportunista após P1
P6 (prova)                   ← contínuo; fecha o plano
```

## Critério de conclusão

O plano P termina quando um agente externo, partindo de um pedido em linguagem
natural, entrega os projetos canônicos cumprindo os seis critérios de
qualidade, com `scripts/testar.ps1` integral e o benchmark ponta a ponta
demonstrando paridade de capacidade com o concorrente **nas tarefas de Part
Design**, mantendo todas as garantias que ele não tem.
