# Ambiente de Sketch

O catálogo possui 24 ferramentas para criar, restringir, editar e inspecionar
perfis 2D nos planos XY, XZ e YZ. Entradas e saídas são JSON simples; nenhuma
ferramenta executa macro ou Python.

## Organização

| Grupo | Ferramentas |
| --- | --- |
| Base | `cad.create_empty_sketch`, `cad.get_sketch_info` |
| Geometria | `add_sketch_line`, `polyline`, `circle`, `arc`, `ellipse`, `rectangle`, `slot`, `regular_polygon` |
| Referência | `cad.add_sketch_external_geometry`, `cad.toggle_sketch_construction` |
| Restrições | `add_sketch_geometric_constraint`, `add_sketch_dimensional_constraint`, alteração, modo dirigente e exclusão |
| Edição | mover, copiar, espelhar, aparar, estender, filetar e excluir geometria |

Os nomes completos e schemas devem ser consultados por `available_cad_tools`.

## Fluxo recomendado

1. Crie o Sketch e guarde o nome retornado.
2. Adicione geometria e guarde `added_geometry`.
3. Aplique relações geométricas antes das cotas.
4. Consulte `cad.get_sketch_info` para verificar solver e graus de liberdade.
5. Ajuste cotas ou edite a geometria.
6. Confirme que o perfil está válido e fechado.
7. Use pad, revolução, loft ou sweep.

Índices começam em zero. Geometrias externas usam IDs negativos; `-1` e `-2`
são os eixos internos. Exclusão e trim podem renumerar itens, portanto consulte o
Sketch novamente antes da próxima edição baseada em índice.

## Restrições

Relações disponíveis incluem horizontal, vertical, paralela, perpendicular,
tangente, igual, coincidente, concêntrica, ponto-no-objeto e bloqueio. Cotas
incluem comprimento, raio, diâmetro, ângulo e distâncias total, X e Y.

Ângulos usam graus; demais dimensões usam milímetros. Cotas podem ser dirigentes
ou de referência.

## Planos laterais

`cad.create_empty_sketch` aceita `xy`, `xz` ou `yz` e offset. `cad.pad_sketch`
extruda na normal do próprio plano, não sempre no eixo Z global.

## Segurança

Cada edição valida argumentos, abre uma transação, recalcula o solver e confirma
somente quando o Sketch e o documento permanecem válidos. Falhas abortam a
operação e `cad.undo` continua disponível.

## Testes

`tests/freecad_sketch_smoke.py` cobre os três planos, primitivas, construção,
referências, restrições, edição, inspeção, pad e undo no FreeCAD real. Marcador:
`FREECAD_SKETCH_SMOKE_OK`.

O benchmark `benchmarks/agent-corpus-sketch-v1.json` mede recuperação das 24
capacidades e bloqueio de pedidos inseguros.
