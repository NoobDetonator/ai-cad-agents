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

## Estado atual — M0 a M7 concluídos

O Workbench **AI CAD** abre um painel funcional dentro do FreeCAD. O modo local
entende comandos fechados; o modo DeepSeek opcional interpreta linguagem natural,
seleciona ferramentas PT/EN e pode executar leituras em um loop limitado. Ambos,
assim como o MCP, usam o mesmo `ToolRegistry` com 90 ferramentas.

O produto já consegue:

- inspecionar documento, seleção, contexto, objetos, medidas, distância e dependências;
- resolver nomes e labels sem aceitar ambiguidades;
- listar parâmetros editáveis e capturar a vista sob demanda;
- criar e alternar documentos, salvar `.FCStd` e exportar STL/STEP;
- criar caixa, cilindro, cone, esfera, toro, placa, sketches retangular e circular constrangidos e pad;
- duplicar ou excluir com proteção de dependências, renomear, alterar dimensões
  permitidas e aplicar transformações absolutas ou relativas;
- criar furos passantes, com rebaixo, escareados e roscados, além de padrões de
  furos retangulares ou circulares;
- executar união, corte e interseção com operandos explícitos;
- aplicar filete e chanfro por assinatura geométrica de aresta;
- criar revolução, loft e sweep sobre trajetória controlada;
- criar engrenagens retas e helicoidais com perfil involuto oficial, fase,
  módulo, dentes, ângulo de pressão, espessura e furo controlados;
- criar coroa interna involuta, porta-planetas e rolamento radial, aplicar
  backlash aos flancos, alinhar e analisar interferências da montagem;
- criar rolamentos rígido de esferas, axial e de rolos cilíndricos, bem como
  rolamento capturado e bucha com folgas explícitas para impressão 3D;
- criar roscas externas e internas estilo ISO 60° voltadas a impressão 3D;
- espelhar e repetir sólidos em padrões lineares e polares;
- construir placa de fixação, flange, pad retangular, eixo escalonado e polia
  plana por receitas confiáveis;
- aprovar uma mutação ou um plano de duas a oito operações e desfazê-lo;
- projetar o mesmo catálogo, receitas, prompts e capturas pela ponte MCP segura.
- registrar e exportar localmente o histórico redigido de ações, planos,
  aprovações, resultados, validações, commits, aborts e undos;
- exportar um objeto sólido validado como STL ou STEP para um destino
  explícito, com confirmação, sem sobrescrita silenciosa e com checksum.

Todas as mutações são chamadas estruturadas, autorizadas pelo painel,
transacionais,
recalculadas e validadas. Texto do modelo nunca vira Python, macro ou shell. A
chave DeepSeek só é solicitada para uso real e fica no cofre do Windows.

No uso normal, o FreeCAD 1.1.1 instalado é aberto pelo próprio Windows e o
Workbench **AI CAD** inicia com aceitação automática visível para mutações. O
usuário pode desmarcá-la para exigir confirmação manual; exportações continuam
manuais. Ambos os caminhos preservam validação, auditoria e reversibilidade.

## Limites honestos do corte atual

O corte atual cobre modelagem mecânica demonstrável, mas ainda não promete
“qualquer coisa que o FreeCAD modele”. As features derivadas guardam seus objetos
de origem e são reversíveis, porém ainda são BReps controlados: não formam uma
árvore Part Design completa que se recomputa automaticamente depois de qualquer
edição. Os sketches retangular e circular gerados pelas ferramentas atuais são
constrangidos; a engrenagem helicoidal aproxima o helicoide por seções loftadas;
as roscas são voltadas a impressão 3D, não a uma promessa de conformidade de
fabricação. O sweep aceita a trajetória estruturada registrada, não caminhos
arbitrários. Superfícies, chapas, assemblies, desenhos técnicos, CAM e FEM ficam
fora do escopo atual.

A exportação STL/STEP de um objeto por vez já existe. Checagens configuráveis de
fabricação, prévia do artefato e exportação de vários objetos não fazem parte da
baseline M0–M7 e não estão vinculadas a um marco futuro ativo.

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

## Direção de manutenção

M0 a M7 estão concluídos e não há próximo marco automático. O produto permanece
MCP primeiro: o servidor, o catálogo seguro e a integração com o FreeCAD recebem correções e
incrementos aprovados por necessidade concreta. O modo DeepSeek, o seletor e o
loop interno permanecem em manutenção, sem expansão multi-provedor.

Qualquer incremento novo deve preservar o `ToolRegistry` único, schemas pequenos,
confirmação humana, transações, validação, rollback, auditoria e testes fora do
FreeCAD. A quantidade de ferramentas não é uma meta isolada; cobertura nova deve
corresponder a tarefas reais e métricas reproduzíveis.
