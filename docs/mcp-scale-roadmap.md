# TALOS — E1: MCP em escala

## Estado

Marco aprovado. A baseline M0–M7 permanece concluída e estável. E1 inicia uma
linha nova de evolução; não renomeia nem reabre os marcos antigos.

A ordem de implementação de capacidade foi substituída pelo
[plano P — Part Design profissional](partdesign-roadmap.md). As frentes E1 já
entregues permanecem válidas; as pendentes ficam adiadas até o P concluir.

Já foram concluídos a descoberta escalável, os erros recuperáveis, a captura
multivista e o corte visual seguro por plano. E1.2 continua em execução.

## Objetivo

Permitir que agentes externos usem progressivamente quase todo o FreeCAD sem
receber centenas de schemas em cada interação, sem depender de Python arbitrário
e sem perder confirmação, transação, validação, rollback ou auditoria.

O resultado esperado é um núcleo MCP pequeno e estável sobre um catálogo interno
expansível, com planos declarativos, inspeção visual, diagnóstico estruturado e
pacotes de capacidade por domínio do FreeCAD.

## Diagnóstico inicial

A baseline possui:

- 92 ferramentas no `ToolRegistry`;
- 17 ferramentas de leitura, 71 de modificação e quatro de exportação;
- aproximadamente 102 KiB no catálogo completo serializado;
- um snapshot de contexto versionado e paginado;
- seleção local PT/EN;
- planos imutáveis de duas a oito mutações;
- confirmação visível, rollback, auditoria e captura PNG.

Essa base é segura, mas o catálogo completo não escala linearmente. Com centenas
de capacidades, o principal problema deixa de ser criar ferramentas e passa a
ser descobrir, compor, executar e verificar as ferramentas corretas com pouco
contexto e poucas viagens MCP.

## Princípios

1. O agente externo continua sendo a IA; não expandir a IA embutida.
2. O FreeCAD permanece adaptador geométrico, nunca camada de regras.
3. Não mapear cada botão do FreeCAD diretamente para uma ferramenta MCP.
4. Manter uma fachada MCP pequena mesmo quando o catálogo interno crescer.
5. Carregar schemas completos somente sob demanda.
6. Preferir planos tipados e receitas a sequências improvisadas.
7. Não executar Python, macros, shell ou comandos arbitrários.
8. Toda mutação continua transacional, validada, auditada e reversível.
9. Imagem complementa medidas e validação; nunca é a única evidência.
10. Recursos pesados usam progresso, cancelamento, limites e cache.
11. Compatibilidade com versões e módulos do FreeCAD deve ser explícita.
12. Incrementos só avançam quando medidos em projetos canônicos.

## Arquitetura-alvo

```text
agente externo
  → fachada MCP pequena e estável
  → descoberta contextual e schemas sob demanda
  → CAD-IR: plano intermediário tipado
  → política, preflight, aprovação e checkpoints
  → ToolRegistry compartilhado
  → pacote de capacidade do domínio
  → adaptador FreeCAD
  → transação, recompute e validação
  → inspeção estruturada e recursos visuais
```

### Fachada MCP

A fachada deve convergir para poucas operações de alto nível:

| Operação | Responsabilidade |
| --- | --- |
| `search_cad_capabilities` | recuperar cartões compactos e relevantes |
| `describe_cad_capabilities` | carregar schemas completos sob demanda |
| `get_cad_context` | obter estado, seleção e objetos relevantes |
| `get_cad_changes` | retornar apenas mudanças desde um token |
| `compile_cad_plan` | validar e congelar um plano declarativo |
| `preview_cad_plan` | simular efeitos antes da aprovação |
| `execute_cad_plan` | executar fases autorizadas |
| `get_cad_task` | acompanhar trabalho demorado |
| `cancel_cad_task` | cancelar em ponto seguro |
| `inspect_cad_model` | validar, medir, analisar e capturar |
| `export_cad_artifact` | salvar ou exportar com autorização explícita |

As ferramentas MCP atuais permanecem compatíveis durante a migração.

## Frente 1 — descoberta escalável

### Busca compacta

`search_cad_capabilities` recebe texto, contexto opcional, família, risco,
limite e cursor. Retorna cartões pequenos, não os schemas completos.

Cada cartão contém:

- nome e título;
- resumo curto;
- família e risco;
- aliases principais;
- relevância e motivos do ranking;
- disponibilidade no FreeCAD atual;
- custo estimado;
- indicação de receita relacionada.

### Descrição sob demanda

`describe_cad_capabilities` recebe nomes retornados pela busca e entrega:

- schema de entrada;
- schema de saída;
- descrição operacional;
- exemplos;
- risco e efeitos;
- requisitos de versão e módulo;
- ferramentas normalmente usadas antes e depois;
- erros estruturados previstos.

### Catálogo em níveis

1. famílias e contagens;
2. cartões encontrados;
3. schemas completos das capacidades escolhidas;
4. referências pesadas apenas por recurso MCP.

### Ranking híbrido

Combinar:

- termos e frases PT/EN;
- aliases, tags, exemplos e família;
- tipos dos objetos selecionados;
- objetos alterados recentemente;
- Workbenches e módulos disponíveis;
- compatibilidade entre capacidades;
- risco e segurança do pedido;
- desempenho em benchmarks anteriores.

O seletor lexical atual permanece como fallback determinístico. Busca semântica
local pode ser adicionada depois, sem ligar o produto a um provedor de IA.

## Frente 2 — resultados e erros estruturados

Todos os resultados MCP devem aproveitar `outputSchema` e conteúdo estruturado.
Erros de domínio devem trazer código, categoria e recuperação possível:

```json
{
  "code": "HOLE_OUTSIDE_TARGET",
  "category": "geometry",
  "retryable": true,
  "safe_state_restored": true,
  "argument": "x",
  "allowed_range": [-50, 50],
  "suggested_actions": [
    {"action": "change_argument", "argument": "x", "recommended": 40}
  ]
}
```

Categorias mínimas:

- argumento inválido;
- objeto ausente ou ambíguo;
- estado ou topologia obsoleta;
- conflito de restrições;
- geometria inválida ou falha do kernel;
- interferência;
- capacidade indisponível;
- GUI ocupada ou ponte desconectada;
- timeout ou cancelamento;
- exportação recusada.

Leituras idempotentes podem ser repetidas. Mutações nunca são repetidas às
cegas. Depois de duas correções sem sucesso, o agente deve parar e apresentar
evidências.

## Frente 3 — inspeção visual

### Captura em lote

`cad.capture_views` já gera até oito vistas padrão em uma chamada, com câmera e
preferência de animação restauradas ao final:

- isométrica;
- frente, traseira, topo e inferior;
- direita e esquerda.

Direção personalizada e folha de contato permanecem incrementos desta frente.

### Vista em corte

`cad.capture_section_view` já cria uma inspeção não destrutiva por plano XY, XZ
ou YZ, com offset, inversão do lado mantido e enquadramento. O corte é apenas
visual, não fecha as faces seccionadas, não substitui um corte preexistente e
restaura o viewport mesmo em falha.

Planos por face, datum ou ponto e normal, além do preenchimento opcional das
faces seccionadas, permanecem incrementos desta frente.

### Outros modos

- transparência controlada;
- isolamento de objetos;
- vista explodida temporária;
- linhas ocultas, arestas e silhueta;
- antes/depois;
- interferências e folgas destacadas;
- labels numerados.

### Dados auxiliares para visão

Além do RGB, avaliar:

- máscara de ID por objeto;
- profundidade;
- normais;
- contornos;
- bounding boxes em pixels;
- legenda de cores e objetos visíveis.

### Seleção adaptativa de ângulos

Escolher automaticamente vistas pelo ganho de informação: oclusão, faces
reveladas, features recentes, simetria, elementos internos e redundância entre
capturas.

### Inspetor unificado

`inspect_cad_model` já entrega a primeira versão unificada na fachada MCP:

- contexto e token inicial;
- validade do documento;
- medidas de até oito objetos;
- detalhes e dependências opcionais;
- até quatro vistas como recursos MCP;
- token final e detecção de edição concorrente;
- resposta parcial estruturada quando uma leitura falha.

Interferência, folga adaptativa, findings de domínio e cortes automáticos
continuam incrementos do inspetor.

## Frente 4 — CAD-IR e composição

Criar uma representação intermediária declarativa e fechada. Passos devem poder
referenciar resultados anteriores sem prever nomes:

```json
{
  "steps": [
    {
      "id": "base",
      "tool": "cad.create_plate",
      "arguments": {"length": 100, "width": 60, "thickness": 5}
    },
    {
      "id": "holes",
      "tool": "cad.create_rectangular_hole_pattern",
      "arguments": {
        "object": {"$ref": "base.object"},
        "diameter": 4,
        "rows": 2,
        "columns": 2
      }
    }
  ]
}
```

Recursos previstos:

- referências tipadas `$ref`;
- DAG e ordenação topológica;
- unidades explícitas;
- frames e coordenadas locais;
- expressões matemáticas limitadas;
- padrões controlados;
- pós-condições;
- custo previsto;
- requisitos de módulos;
- política de rollback e checkpoints.

Nenhuma expressão pode executar código.

## Frente 5 — preflight, preview e fases

Antes de modificar:

1. validar schemas e unidades;
2. resolver referências;
3. verificar viabilidade dimensional;
4. estimar custo e subgrafo afetado;
5. produzir preview fantasma quando útil;
6. apresentar efeitos e suposições;
7. congelar o plano para aprovação.

Projetos grandes são divididos em fases, não em um plano monolítico:

```text
referências e sketches
  → checkpoint
volumes principais
  → checkpoint
furos e acabamentos
  → checkpoint
inspeção e entrega
```

Falha em uma fase desfaz somente a fase problemática, preserva checkpoints
válidos e recompila o trecho afetado.

## Frente 6 — contexto incremental e identidade

### Diferenças desde um token

`cad.get_changes_since` retorna objetos criados, alterados e removidos, seleção,
token novo e possíveis conflitos. O agente não relê o documento inteiro.

### Níveis de contexto

- L0: documento, seleção e resumo;
- L1: objetos relevantes;
- L2: parâmetros e dependências;
- L3: topologia e referências;
- L4: malhas, imagens e dados pesados.

### Identidade estável

Objetos recebem IDs opacos. Faces e arestas usam seletores semânticos, por
exemplo maior face plana superior ou aresta circular de diâmetro esperado. Uma
referência que não pode ser revalidada falha como obsoleta; nunca escolhe outra
topologia silenciosamente.

## Frente 7 — unidades, frames e montagem

Aceitar quantidades com unidade e normalizar internamente. Introduzir:

- frame global;
- frame local do objeto;
- frame de face ou datum;
- eixos e planos nomeados;
- coordenadas relativas a outro componente.

Isso prepara montagem, BIM, robótica e operações fora do plano global.

## Frente 8 — validação por domínio

Perfis de inspeção:

- geral: forma, sólidos, dependências, dimensões e features vazias;
- impressão 3D: paredes, overhang, pontes, folgas e volumes fechados;
- usinagem: raios, alcance, undercuts, sobremetal e profundidade de furos;
- montagem: interferência, contato, graus de liberdade e colisão em movimento;
- chapa: espessura, dobra, alívio e planificação;
- FEM: material, restrições, cargas, malha e unidades.

## Frente 9 — tarefas, progresso e cancelamento

Operações demoradas devem informar progresso por etapa, aceitar cancelamento em
pontos seguros e impor limites de concorrência, duração e memória.

Usar recursos MCP padrão quando o cliente suportar. Como Tasks ainda é uma parte
experimental do protocolo, manter o polling atual como fallback compatível.

## Frente 10 — desempenho

### Telemetria ponta a ponta

`get_mcp_performance_snapshot` registra, somente em memória, bytes/tokens
estimados, latência do MCP e bridge, fila da GUI, confirmação e execução no
FreeCAD. O contrato opcional `BridgeTiming` mantém clientes anteriores
compatíveis e evita misturar espera humana com custo geométrico.

### Recompute incremental

Usar o grafo de dependências para recalcular primeiro o subgrafo afetado. Fazer
validação completa no checkpoint e obrigatoriamente antes de salvar ou exportar.

### Cache por fingerprint

Cachear leituras puras por fingerprint do documento e configuração:

- medidas e bounding boxes;
- dependências;
- malhas;
- capturas;
- matriz de interferência;
- ranking de capacidades.

### Paralelismo permitido

Mutações na GUI permanecem serializadas. Ranking, schemas, compilação de plano,
folhas de contato, auditoria e análise sobre snapshots imutáveis podem rodar fora
da thread da GUI.

## Frente 11 — risco e aprovação

Preservar `read`, `modify` e `export`, acrescentando facetas:

- efeito no documento;
- reversibilidade;
- efeito no filesystem;
- custo computacional;
- dependência de processo externo;
- necessidade de GUI;
- destrutividade.

Aceitação automática vale somente para mutações reversíveis, sem efeito externo,
dentro de limites de custo e com rollback. Exportação, sobrescrita, fechamento
de documento não salvo, solver e CAM continuam manuais.

## Frente 12 — pacotes de capacidade

Cada pacote contém manifesto, schemas, adaptador, validadores, receitas, testes,
benchmarks, versões suportadas e migrações.

Ordem de expansão:

1. fundamento e Part Design paramétrico;
2. Sketcher completo;
3. inspeção, Assembly e TechDraw;
4. Surface, curvas e chapa;
5. Mesh, Points e Reverse Engineering;
6. Spreadsheet e expressões;
7. FEM e pós-processamento;
8. Path/CAM e simulação;
9. Draft, Arch/BIM, Robot e addons aprovados.

O servidor detecta FreeCAD, módulos e addons instalados e publica somente
capacidades realmente disponíveis.

## Estratégia MCP

- mapear resultados internos para `structuredContent` e `outputSchema`;
- usar recursos binários e links para imagens e artefatos;
- anotar recursos com prioridade, público, tamanho e data;
- paginar catálogos e tarefas;
- notificar mudanças de catálogo e recursos;
- usar progresso e cancelamento padrão;
- usar elicitação estruturada quando o cliente suportar;
- manter fallbacks para clientes anteriores;
- não adicionar sampling nem IA multi-provedor ao Workbench.

## Testes

Cada capacidade exige:

1. contrato e schema;
2. teste neutro com adaptador falso;
3. smoke no FreeCAD real quando geométrica;
4. entradas inválidas e limites;
5. transação, undo e fingerprint;
6. dependências e pós-condições;
7. medidas geométricas;
8. evidência visual quando aplicável;
9. benchmark de recuperação;
10. compatibilidade de versão.

Testes adicionais:

- property-based para combinações dimensionais;
- metamórficos para volume, transformação, unidades e save/reopen;
- caos para desconexão, timeout, cancelamento e edição concorrente;
- regressão visual por silhueta, máscara e bounding boxes;
- projetos canônicos completos.

## Projetos canônicos

- case eletrônico com tampa;
- suporte curvo baseado em desenho;
- fidget spinner print-in-place;
- estágio planetário;
- redutor com rolamentos;
- peça torneada;
- suporte de chapa;
- montagem com TechDraw;
- malha importada e reparada;
- análise FEM simples;
- operação CAM controlada.

## Métricas

| Métrica | Meta inicial |
| --- | ---: |
| ferramenta correta entre as oito recuperadas | pelo menos 98% |
| payload de ferramentas por interação | no máximo 20 KiB |
| rollback restaurando fingerprint | 100% |
| mutação inválida confirmada | zero |
| referência obsoleta detectada antes da mutação | 100% |
| primeiro progresso em tarefa longa | menos de 1 s |
| overhead MCP/ponte fora do FreeCAD | menos de 200 ms |
| câmera e visibilidade restauradas após inspeção | 100% |
| redução de chamadas em peças comuns | 40% a 60% |
| exportação sem autorização explícita | zero |

## Ondas de entrega

| Onda | Estado |
| --- | --- |
| E1.1 — descoberta escalável | concluída |
| Base transversal — erros recuperáveis | concluída |
| E1.2 — percepção visual | em execução |
| E1.3 — CAD-IR | pendente |
| E1.4 — parametricidade nativa | pendente |
| E1.5 — pacotes de Workbench | pendente |
| E1.6 — robustez contínua | pendente |

### E1.1 — descoberta escalável

- busca compacta e paginada;
- schemas sob demanda;
- testes de payload, ranking e segurança;
- documentação do fluxo novo.

### Base transversal — erros recuperáveis

- categorias e ações de recuperação compartilhadas pela ponte e pelo MCP;
- estado seguro explícito para falhas anteriores à execução e rollback;
- transporte interrompido marcado como estado desconhecido;
- erros de leitura preservados como resposta estruturada;
- mensagens de domínio curtas, redigidas e sem detalhes internos.

### E1.2 — percepção visual

- captura em lote; **concluída**
- vista em corte XY/XZ/YZ com offset; **concluída**
- transparência e isolamento;
- folha de contato;
- inspetor unificado inicial; **concluído**

### E1.3 — CAD-IR

- referências entre passos;
- DAG;
- unidades e frames;
- preflight, preview e fases.

### E1.4 — parametricidade nativa

- Body e features Part Design;
- datums e binders;
- referências estáveis;
- edição por dimensão-base.

### E1.5 — pacotes de Workbench

- Assembly e TechDraw;
- superfícies, chapa e malha;
- Spreadsheet, FEM e CAM;
- BIM e especialidades.

### E1.6 — robustez contínua

- tarefas MCP;
- cache e recompute incremental;
- matriz de versões;
- chaos tests e metas de desempenho.

## Ordem de implementação

1. `search_cad_capabilities`;
2. `describe_cad_capabilities`;
3. erros estruturados; **concluído**
4. `cad.capture_views`; **concluído**
5. `cad.capture_section_view`; **concluído**
6. transparência, isolamento e restauração da câmera;
7. `inspect_cad_model`; **concluído**
8. referências entre passos;
9. preflight e preview;
10. pacotes por Workbench;
11. Part Design paramétrico;
12. expansão gradual para o restante do FreeCAD.

## Critério de conclusão de cada onda

Uma onda só termina quando:

- contratos estão versionados;
- testes neutros e reais passam;
- rollback e auditoria permanecem corretos;
- métricas atingem a meta definida;
- projetos canônicos demonstram o ganho;
- documentação está atualizada;
- `scripts/testar.ps1` passa integralmente.

## Referências oficiais

- [MCP — Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [MCP — Resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources)
- [MCP — Progress](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/progress)
- [MCP — Cancellation](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/cancellation)
- [MCP — Tasks](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks)
- [MCP — Elicitation](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation)
- [FreeCAD — Workbench Framework](https://freecad.github.io/SourceDoc/d7/dc3/group__workbench.html)
- [FreeCAD — Modules](https://freecad.github.io/SourceDoc/modules.html)
- [FreeCAD — Document API](https://freecad.github.io/SourceDoc/d8/d3e/classApp_1_1Document.html)
- [FreeCAD — View3D API](https://freecad.github.io/SourceDoc/da/d75/classGui_1_1View3DInventor.html)
