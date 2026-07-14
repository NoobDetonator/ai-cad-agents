# Visão do produto

Um servidor MCP seguro que dá a agentes de IA externos — Claude Code, Codex,
Cursor e qualquer cliente MCP — ferramentas estruturadas, validadas e
reversíveis para modelar peças reais no FreeCAD.

## Estratégia: MCP primeiro

Decisão de 14 de julho de 2026. O produto principal é o servidor MCP; o
cérebro vem do agente externo que o usuário já usa e já paga. Consequências:

1. **O agente externo é a IA.** Não construiremos suporte multi-provedor
   interno (OpenAI, Anthropic, Gemini etc.). O usuário escolhe a plataforma ao
   escolher o agente — Claude Code usa Claude, Codex usa OpenAI, Cursor usa o
   modelo configurado nele. Zero chaves de API para nós gerenciarmos.
2. **A IA embutida entra em modo manutenção.** O modo DeepSeek, o
   `ToolSelector` e o `AgentTurnController` continuam funcionando e testados,
   mas não recebem novas funcionalidades. Permanecem como modo standalone
   opcional para quem não usa um agente externo.
3. **O painel vira superfície de aprovação.** Sua função principal passa a ser
   mostrar o que o agente externo quer fazer, exibir o plano, colher a
   confirmação humana e apresentar o resultado — não conversar.
4. **Cada hora nova vai para a ponta que o agente toca:** mais ferramentas de
   modelagem, exportação de arquivos, feedback visual e documentação de
   integração.

O diferencial contra os MCPs de CAD existentes é estrutural: eles executam
Python arbitrário dentro do FreeCAD; nós expomos ferramentas pequenas com
schema, validação, transação, confirmação humana, rollback e auditoria. Um
agente que chama `cad.create_through_hole` com argumentos validados acerta
muito mais do que um que escreve um script `Part` de 40 linhas no escuro.

## Primeiro nicho

Peças mecânicas para impressão 3D e fabricação leve:

- suportes, caixas e tampas;
- adaptadores e flanges;
- placas, gabaritos e peças furadas;
- componentes formados por sketches, pads e booleanas controladas.

## Fluxo obrigatório

1. Entender intenção, referência e restrições.
2. Ler o estado real do documento quando necessário.
3. Expor suposições e pedir seleção quando houver ambiguidade.
4. Criar um plano estruturado somente com ferramentas registradas.
5. Mostrar a revisão e exigir confirmação para mutações.
6. Aplicar transações, recalcular e validar.
7. Confirmar o resultado ou reverter toda a unidade aprovada.

## Estado atual — M5 concluído

O Workbench **AI CAD** abre um painel funcional dentro do FreeCAD. O modo local
entende comandos fechados; o modo DeepSeek opcional interpreta linguagem natural,
seleciona ferramentas PT/EN e pode executar leituras em um loop limitado. Ambos,
assim como o MCP, usam o mesmo `ToolRegistry` com 28 ferramentas.

O produto já consegue:

- inspecionar documento, seleção, contexto, objetos, medidas e dependências;
- resolver nomes e labels sem aceitar ambiguidades;
- listar parâmetros editáveis e capturar a vista sob demanda;
- criar caixa, cilindro, placa, sketch retangular e pad;
- renomear, alterar dimensões permitidas, mover e rotacionar objetos;
- criar furos passantes e padrões retangulares ou circulares;
- executar união, corte e interseção com operandos explícitos;
- aplicar filete e chanfro por assinatura geométrica de aresta;
- criar engrenagem reta externa com perfil involuto oficial do FreeCAD, módulo,
  dentes, ângulo de pressão, espessura e furo controlados;
- construir placa de fixação, flange e pad retangular por receitas confiáveis;
- aprovar uma mutação ou um plano de duas a oito operações e desfazê-lo;
- projetar o mesmo catálogo, receitas, prompts e capturas pela ponte MCP segura.
- registrar e exportar localmente o histórico redigido de ações, planos,
  aprovações, resultados, validações, commits, aborts e undos.

Todas as mutações são chamadas estruturadas, confirmadas, transacionais,
recalculadas e validadas. Texto do modelo nunca vira Python, macro ou shell. A
chave DeepSeek só é solicitada para uso real e fica no cofre do Windows.

Durante desenvolvimento, um lançador separado oferece confirmação automática
visível e limitada à sessão para acelerar testes. Ele preserva toda a validação e
reversibilidade e não muda o padrão seguro do lançador normal.

## Limites honestos do corte atual

O M4 cobre modelagem mecânica básica de forma demonstrável, mas ainda não promete
“qualquer coisa que o FreeCAD modele”. As features derivadas guardam seus objetos
de origem e são reversíveis, porém ainda são BReps controlados: não formam uma
árvore Part Design completa que se recomputa automaticamente depois de qualquer
edição. O sketch retangular não é totalmente constrangido, e ainda faltam loft,
sweep, revolução, superfícies, chapas, assemblies, desenhos técnicos, CAM e FEM.

Ainda faltam validações de fabricação e exportação STEP/STL. Esses itens pertencem
ao M6.

## Diferenciais pretendidos

- ferramentas estruturadas em vez de execução de código gerado — a diferença
  entre demo e ferramenta confiável;
- confirmação humana, transações e rollback como argumento de venda para
  agentes autônomos;
- operação local, privada e explicável;
- mesma capacidade no painel e via MCP, por um único `ToolRegistry`;
- ferramentas pequenas que o agente escolhe com pouco contexto;
- receitas reutilizáveis no lugar de código gerado;
- feedback visual e mensurável para o agente se autocorrigir;
- histórico completo das decisões sem guardar segredos;
- validação antes de exportar ou fabricar.

## Direção seguinte

O M5 concluiu o histórico e a auditoria local versionados. Daqui em diante o
roteiro segue a estratégia MCP primeiro:

- **M6 — MCP como produto**: exportação STL/STEP controlada fecha o fluxo
  "pedido em linguagem natural → arquivo fabricável"; documentação e
  configuração de integração para Claude Code, Codex e Cursor; descrições de
  ferramenta otimizadas para agentes externos.
- **M7 — Cobertura de modelagem**: sketch constrangido, revolução, sweep,
  loft, mais receitas e feedback visual pós-mutação, ampliando o que um agente
  consegue modelar sozinho.
- **M8 — Lançamento público**: instalação simples, documentação de usuário
  final, demonstração gravada e abertura do repositório com divulgação na
  comunidade FreeCAD.
