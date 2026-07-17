# Estudo — neka-nat/freecad-mcp

Análise do projeto concorrente mais popular (~1.3k estrelas, MIT, ~2.500 linhas).
Clone local para leitura em `.study/freecad-mcp` (fora do Git). Este documento
registra o que aprender, o que adotar com governança e o que rejeitar.

## Arquitetura em uma frase

Servidor MCP fino (FastMCP) → XML-RPC na porta fixa 9875 → addon na GUI do
FreeCAD que executa criação genérica de objetos, edição por dicionário de
propriedades e Python arbitrário, devolvendo screenshot após cada mutação.

## De onde vem a amplitude dele (a descoberta central)

Não é principalmente do `execute_code`. O mecanismo real é **reflexão sem
allowlist** em `create_object`/`edit_object`:

- `create_object(obj_type, properties)` chama `doc.addObject(obj_type)` para
  qualquer tipo (`Part::*`, `Draft::*`, `PartDesign::*`, `Fem::*`) e aplica um
  `setattr` por chave do dicionário (`object_factory.py`, ~110 linhas).
- `property_mapper.py` (~140 linhas) converte JSON → tipos FreeCAD:
  `Placement` aninhado, `Vector`, nomes de objeto → referências reais para
  `Base`/`Tool`/`Source`/`Profile`, lista `References` para FEM e
  `ShapeColor` no ViewObject.
- O conhecimento do modelo de propriedades do FreeCAD vem do treinamento do
  LLM; a ferramenta é só um refletor burro. ~250 linhas entregam a maior parte
  do valor percebido do `execute_code`.

Consequência para o TALOS: entre "uma ferramenta escrita à mão por operação" e
"exec arbitrário" existe um terceiro caminho — **reflexão governada por
allowlist tipada**. É a aposta central do
[roadmap Part Design](partdesign-roadmap.md).

## Como ele ensina o LLM a modelar

- `ASSET_CREATION_STRATEGY` (`prompt_text.py`, 28 linhas): confira o estado com
  `get_objects` → biblioteca de partes primeiro → primitivas → `edit_object` →
  verifique com `get_object` → `execute_code` como último recurso.
- Docstrings com **exemplos JSON completos de chamada** (cilindro com
  `Placement` + rotação + cor; cadeia FEM inteira: análise → material →
  restrição → malha Gmsh). O exemplo completo ensina mais que descrição longa.
- Checklist de pré-requisitos na docstring de `run_fem_analysis`.

Adotar: exemplos JSON completos nas descrições TALOS e um prompt de
metodologia por família muito mais forte que o dele.

## Ideias que valem adoção (com correções)

| Ideia | Onde está | Correção necessária no TALOS |
| --- | --- | --- |
| Biblioteca de partes | `parts_library.py` (38 linhas) | valida caminho (o dele tem path traversal — `relative_path` sem sanitização escapa da pasta via `..`); mutação compensável normal |
| Mapeador JSON→FreeCAD | `property_mapper.py` | vira módulo do adaptador, mas só propriedades em allowlist |
| Cadeia FEM como fluxo guiado | `object_factory.py` + `fem_executor.py` | vira receita com pré-requisitos validados, não objetos soltos |
| Screenshot pós-mutação opcional | `operations/core.py` | já coberto por `capture_views`/`inspect_cad_model`, com limites |

## O que rejeitar conscientemente

- `execute_code`/`execute_code_async`: Python irrestrito na GUI, incentivado
  com "Always Allow" no guia oficial. Incompatível com o produto.
- Segurança: só filtro de IP (`ip_filter.py`), **sem token de autenticação**,
  porta fixa — qualquer processo local executa Python no FreeCAD.
- Sem transação, undo, auditoria, validação de argumento ou erro estruturado;
  falhas voltam como string crua de exceção.
- Fecha/destrói documentos sem confirmação (o próprio guia do MakeForm alerta).

## Números para calibrar

| | freecad-mcp | TALOS hoje |
| --- | ---: | ---: |
| Linhas de código | ~2.500 | ~17.000 |
| Ferramentas MCP | 14 | 92 + fachada |
| Cobertura do FreeCAD | total (via reflexão + exec) | curada |
| Autenticação | nenhuma | token + HMAC |
| Transação/rollback | não | sim |

A lição não é "escreva menos linhas"; é **onde** ele gasta as linhas: no
mapeador genérico e nos exemplos de docstring — os dois pontos de maior
alavancagem por linha. O TALOS gasta em governança (que ele não tem) e em
schemas manuais (que a reflexão governada pode substituir em parte).
