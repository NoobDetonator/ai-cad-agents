# Visão do produto

Um ambiente CAD paramétrico local, auditável e independente de provedor,
controlável por conversa e por agentes externos.

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

## Estado atual — M4 concluído

O Workbench **AI CAD** abre um painel funcional dentro do FreeCAD. O modo local
entende comandos fechados; o modo DeepSeek opcional interpreta linguagem natural,
seleciona ferramentas PT/EN e pode executar leituras em um loop limitado. Ambos,
assim como o MCP, usam o mesmo `ToolRegistry` com 25 ferramentas.

O produto já consegue:

- inspecionar documento, seleção, contexto, objetos, medidas e dependências;
- resolver nomes e labels sem aceitar ambiguidades;
- listar parâmetros editáveis e capturar a vista sob demanda;
- criar caixa, cilindro, placa, sketch retangular e pad;
- renomear, alterar dimensões permitidas, mover e rotacionar objetos;
- criar furos passantes e padrões retangulares ou circulares;
- executar união, corte e interseção com operandos explícitos;
- aplicar filete e chanfro por assinatura geométrica de aresta;
- construir placa de fixação, flange e pad retangular por receitas confiáveis;
- aprovar uma mutação ou um plano de duas a oito operações e desfazê-lo;
- projetar o mesmo catálogo, receitas, prompts e capturas pela ponte MCP segura.

Todas as mutações são chamadas estruturadas, confirmadas, transacionais,
recalculadas e validadas. Texto do modelo nunca vira Python, macro ou shell. A
chave DeepSeek só é solicitada para uso real e fica no cofre do Windows.

## Limites honestos do corte atual

O M4 cobre modelagem mecânica básica de forma demonstrável, mas ainda não promete
“qualquer coisa que o FreeCAD modele”. As features derivadas guardam seus objetos
de origem e são reversíveis, porém ainda são BReps controlados: não formam uma
árvore Part Design completa que se recomputa automaticamente depois de qualquer
edição. O sketch retangular não é totalmente constrangido, e ainda faltam loft,
sweep, revolução, superfícies, chapas, assemblies, desenhos técnicos, CAM e FEM.

Também ainda faltam auditoria persistente, validações de fabricação e exportação
STEP/STL. Esses itens pertencem aos próximos marcos.

## Diferenciais pretendidos

- operação local, privada e explicável;
- mesma capacidade no chat e via MCP;
- ferramentas pequenas que a IA escolhe com pouco contexto;
- receitas reutilizáveis no lugar de código gerado;
- modelos cada vez mais paramétricos e editáveis;
- histórico completo das decisões sem guardar segredos;
- validação antes de exportar ou fabricar.

## Direção seguinte

M5 adicionará histórico e auditoria local versionados. Depois, M6 cobre validação
de fabricação e exportações controladas, e M7 simplifica instalação e uso diário.
