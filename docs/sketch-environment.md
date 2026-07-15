# Ambiente paramétrico de Sketch

O ambiente de Sketch fornece uma API estruturada para construir, restringir,
editar e inspecionar perfis 2D sem executar Python ou macros enviados pelo
agente. São 24 ferramentas dedicadas no catálogo compartilhado pelo chat e pelo
MCP. Elas complementam os atalhos antigos de sketch retangular e circular.

O objetivo desta camada é cobrir por composição o ciclo fundamental de um
Sketch paramétrico: criar o plano, adicionar geometria, projetar referências,
aplicar relações e cotas, revisar o solver e editar o perfil até ele poder
alimentar pad, revolução, loft ou sweep.

## Organização

Os contratos permanecem independentes do FreeCAD:

- `core/tool_catalog/sketching.py`: nomes, schemas, risco, busca PT/EN e ordem;
- `adapters/freecad/sketches.py`: plano, transação, validação e resultado comum;
- `adapters/freecad/sketch_geometry.py`: criação e edição de geometria;
- `adapters/freecad/sketch_constraints.py`: restrições, cotas e inspeção;
- `application.py`: protocolo e ligação dos handlers ao mesmo `ToolRegistry`.

O adaptador não expõe objetos internos do FreeCAD. Entradas e saídas usam nomes,
coordenadas, índices limitados e dados JSON simples.

## Catálogo

### Criação e geometria

| Ferramenta | Função |
|---|---|
| `cad.create_empty_sketch` | Cria um Sketch nos planos globais XY, XZ ou YZ, com offset opcional. |
| `cad.add_sketch_line` | Adiciona um segmento entre dois pontos. |
| `cad.add_sketch_polyline` | Adiciona de 2 a 256 pontos conectados, com fechamento opcional. |
| `cad.add_sketch_circle` | Adiciona círculo por centro e raio. |
| `cad.add_sketch_arc` | Adiciona arco por centro, raio e ângulos. |
| `cad.add_sketch_ellipse` | Adiciona elipse por raios maior/menor e rotação. |
| `cad.add_sketch_rectangle` | Adiciona retângulo, inclusive rotacionado. |
| `cad.add_sketch_slot` | Adiciona rasgo oblongo por dois centros e largura. |
| `cad.add_sketch_regular_polygon` | Adiciona polígono regular de 3 a 128 lados. |
| `cad.add_sketch_external_geometry` | Projeta uma aresta resolvida de outro objeto como referência externa. |

Todas as geometrias novas aceitam modo normal ou de construção quando aplicável.
Formas compostas retornam a lista `added_geometry`, permitindo usar os índices
nas chamadas seguintes sem adivinhação.

### Restrições paramétricas

| Ferramenta | Função |
|---|---|
| `cad.add_sketch_geometric_constraint` | Horizontal, vertical, paralela, perpendicular, tangente, igual, coincidente, concêntrica, ponto-no-objeto ou bloqueio. |
| `cad.add_sketch_dimensional_constraint` | Comprimento, raio, diâmetro, ângulo, distância, distância X ou distância Y. |
| `cad.set_sketch_constraint_value` | Altera uma cota existente em milímetros ou graus. |
| `cad.set_sketch_constraint_driving` | Alterna uma cota entre dirigente e referência. |
| `cad.delete_sketch_constraint` | Remove uma ou mais restrições por índice. |

Restrições geométricas usam `first_geometry` e, quando necessário,
`second_geometry`. Pontos usam `start`, `end` ou `center`. Cotas de ângulo são
recebidas em graus; as demais dimensões, em milímetros.

### Edição

| Ferramenta | Função |
|---|---|
| `cad.move_sketch_point` | Move início, fim ou centro respeitando as restrições ativas. |
| `cad.toggle_sketch_construction` | Alterna geometria normal e auxiliar. |
| `cad.delete_sketch_geometry` | Exclui geometria e dependências do solver. |
| `cad.trim_sketch_geometry` | Apara linha ou curva no ponto indicado. |
| `cad.extend_sketch_geometry` | Estende início ou fim por um incremento positivo. |
| `cad.fillet_sketch_corner` | Cria filete tangente entre duas geometrias, com trim opcional. |
| `cad.copy_sketch_geometry` | Copia por deslocamento, com clonagem opcional das restrições. |
| `cad.mirror_sketch_geometry` | Espelha pelo eixo horizontal, vertical ou linha de construção. |

### Inspeção

`cad.get_sketch_info` é leitura pura. O resultado inclui plano, contagens,
geometria, modo de construção, restrições, cotas dirigentes/de referência,
mensagens do solver, graus de liberdade, fios fechados, validade e estado de
totalmente restringido. Essa leitura deve ser usada antes de uma edição baseada
em índices e depois de um conjunto de restrições.

## Convenções e fluxo recomendado

1. Crie um Sketch e guarde o `name` retornado.
2. Adicione geometria e guarde os índices de `added_geometry`.
3. Adicione relações geométricas antes das cotas dimensionais.
4. Consulte `cad.get_sketch_info` para verificar graus de liberdade e solver.
5. Ajuste cotas ou pontos; use trim, extensão e filete somente com pontos locais
   inequívocos.
6. Quando o perfil estiver válido e fechado, use pad, revolução, loft ou sweep.

Índices de geometria começam em zero. Geometrias externas usam IDs negativos do
Sketcher; `-1` e `-2` ficam reservados aos eixos internos e a primeira referência
externa começa em `-3`. Índices são estáveis durante adições, mas exclusões podem
renumerar itens posteriores. Por isso, após excluir ou aparar, consulte novamente
`cad.get_sketch_info`.

## Segurança e reversibilidade

Toda ferramenta de modificação:

- valida tipos, limites, valores finitos e referências antes de editar;
- abre uma transação nomeada no documento;
- recalcula e verifica o estado do solver e do documento;
- confirma a transação somente no sucesso;
- aborta integralmente em erro, conflito ou pós-condição inválida;
- permanece reversível pelo mesmo `cad.undo` das demais ferramentas.

O ambiente não oferece execução de Python, macro ou expressão arbitrária.
`cad.get_sketch_info` tem risco de leitura; as outras 23 ferramentas têm risco de
modificação e passam pela política visível de aprovação.

## Testes

`tests/freecad_sketch_smoke.py` executa as operações contra o FreeCAD real. Ele
cobre os três planos, primitivas, construção, geometria externa, restrições,
cotas de referência, cópia, espelho, exclusão, trim, extensão, filete, movimento,
inspeção, criação de um sólido por pad e undo. O sucesso exige o marcador
`FREECAD_SKETCH_SMOKE_OK`.

O corpus `benchmarks/agent-corpus-sketch-v1.json` mede as 24 capacidades e quatro
pedidos inseguros. A suíte unitária também garante catálogo único, schemas
limitados e validação sem depender de uma instalação do FreeCAD.

O teste obrigatório do repositório continua:

```powershell
.\scripts\testar.ps1
```
