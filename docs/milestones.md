# Marcos do projeto

Os marcos M0 a M7 estão concluídos. Este arquivo registra somente o resultado
atual; o histórico detalhado permanece no Git.

## Próximo marco aprovado

**E1 — MCP em escala** está em execução. Ele amplia descoberta, composição,
inspeção e pacotes de capacidades sem criar um marco M8. O plano completo está
em [mcp-scale-roadmap.md](mcp-scale-roadmap.md).

## Resumo

| Marco | Entrega principal | Estado |
| --- | --- | --- |
| M0 | estrutura, configuração, testes e carregamento do Workbench | concluído |
| M1 | chat local seguro, comandos fechados e confirmação visual | concluído |
| M2 | ponte MCP–GUI autenticada e execução na thread Qt | concluído |
| M3 | contexto versionado, seleção de ferramentas, planos e rollback | concluído |
| M4 | contexto visual, receitas e modelagem mecânica básica | concluído |
| M5 | auditoria local, redaction, consulta e exportação | concluído |
| M6 | MCP como produto e exportação STL/STEP controlada | concluído |
| M7 | documentos, Sketch e modelagem mecânica ampliada | concluído |

## Expansões concluídas

- catálogo fundamental com primitivas, edição, medição e distância;
- 24 ferramentas dedicadas ao ambiente paramétrico de Sketch;
- revolução, loft, sweep, padrões, roscas e furos especializados;
- engrenagens, alinhamento, interferência e componentes de montagem;
- rolamentos convencionais e modelos para impressão 3D;
- cinco receitas confiáveis;
- descoberta compacta, paginada e com schemas sob demanda;
- erros recuperáveis com categoria, próxima ação e estado seguro explícito;
- captura multivista com câmera e overlays restaurados;
- corte visual XY/XZ/YZ por offset, sem alterar a geometria;
- framebuffer estabilizado antes da captura para impedir quadros parciais.

O catálogo atual possui 92 ferramentas no mesmo `ToolRegistry`.

## Critérios permanentes

Qualquer incremento deve:

1. partir de uma necessidade concreta;
2. manter regras e schemas independentes do FreeCAD;
3. usar ferramenta registrada, nunca código arbitrário;
4. preservar confirmação, transação, validação, rollback e auditoria;
5. incluir testes neutros e, quando geométrico, teste no FreeCAD real;
6. atualizar documentação e descrições do catálogo;
7. passar por `scripts/testar.ps1`.

## Estado de manutenção da baseline

E1 foi explicitamente aprovado. Trabalho fora de seu plano continua entrando
como correção ou incremento aprovado. O servidor MCP, o catálogo e a integração
com o FreeCAD recebem a prioridade.

DeepSeek, seletor e loop interno permanecem funcionais, mas em manutenção. Não
há plano de suporte multi-provedor dentro do Workbench.

## Limites atuais

- features derivadas são BReps reversíveis, não uma árvore Part Design completa;
- exportação opera sobre um objeto por vez;
- roscas e peças print-in-place exigem validação de fabricação;
- superfície avançada, chapa, desenho técnico, CAM e FEM não fazem parte da baseline;
- assemblies são ferramentas mecânicas controladas, não um ambiente completo de montagem.

## Checklist de desenvolvimento

Antes de alterar: leia `AGENTS.md`, confira o status do Git e preserve mudanças
locais. Durante o trabalho: mantenha schemas pequenos e mutações transacionais.
Antes de concluir: valide testes, documentação, captura quando aplicável e
confirme que nenhum segredo ou artefato gerado entrou no Git.
