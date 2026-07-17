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

### P4 — Metodologia embutida

- Prompt MCP `part_design_methodology`: parâmetros primeiro → sketch mestre
  totalmente restrito → feature base → features secundárias → padrões →
  dressups por último → inspeção por fase → nomes descritivos sempre;
- exemplos JSON completos em toda descrição de ferramenta nova;
- guia por família como recurso MCP (`aicad://guides/partdesign`), carregado
  sob demanda, fora do payload normal.

### P5 — Biblioteca de partes e validação de engenharia

- `cad.list_library_parts` / `cad.insert_library_part` sobre o addon
  parts_library quando instalado — com caminho validado (sem path traversal,
  ao contrário do concorrente), mutação compensável normal;
- massa e centro de gravidade com densidade de material informada;
- perfil de impressão 3D no inspetor: espessura mínima de parede, overhang
  para direção de impressão dada, volume fechado;
- FEM permanece adiado; a cadeia guiada do concorrente vira receita futura.

### P6 — Prova ponta a ponta

- Projetos canônicos remodelados como Bodies paramétricos: case com tampa,
  suporte, flange, estágio planetário;
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
