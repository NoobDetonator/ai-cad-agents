# Visão do produto

Um ambiente CAD paramétrico local, auditável e independente de provedor, controlável por conversa e por agentes externos.

## Primeiro nicho

Peças mecânicas simples para impressão 3D e fabricação leve:

- suportes;
- caixas e tampas;
- adaptadores;
- flanges;
- placas e gabaritos.

## Fluxo obrigatório

1. Entender intenção e restrições.
2. Expor suposições.
3. Criar plano de operações.
4. Gerar prévia.
5. Aplicar em uma transação.
6. Recalcular e validar.
7. Confirmar ou reverter.

## Estado atual

O corte funcional atual cobre o ciclo completo para caixa e cilindro paramétricos:

- o Workbench aparece e abre o painel de chat;
- o pedido local é convertido em uma chamada estruturada;
- o plano é mostrado antes da mutação;
- a interface exige confirmação explícita;
- caixas e cilindros são criados em transações, recalculados e validados;
- a transação é reversível por `desfazer`;
- a mesma lista de capacidades é usada pelo chat e pelo MCP;
- a ponte MCP–GUI executa leituras na thread Qt;
- mutações MCP ficam pendentes até confirmação explícita no painel;
- o M3 já possui contratos neutros e planejamento estruturado sem execução.

A DeepSeek já pode ser ativada explicitamente no painel para interpretar
linguagem natural e propor uma chamada validada pelo registro. O modo permanece
desligado por padrão; leituras podem prosseguir e mutações continuam pendentes
até confirmação visual. O loop atual pode fazer várias leituras e revisar a
resposta, mas não executa mutações por conta própria. Exportação para fabricação
ainda não foi implementada.

O M3.1 também está concluído: resultados e erros do futuro loop possuem contrato
versionado, as etapas podem ser medidas com relógio monotônico sem persistir dados
e um corpus offline de 30 pedidos registra a baseline do parser atual. Isso ainda
não muda o comportamento do painel; fornece a régua segura para o contexto
versionado do M3.2.

O M3.2 está concluído. O contexto agora possui revisão e fingerprints, inclui
seleção, parâmetros, forma, objetos recentes e paginação, e é consumido pela
DeepSeek e pelo MCP por meio da mesma ferramenta de leitura. Uma alteração manual
relevante muda o token; isso prepara a futura recusa de planos obsoletos sem
liberar nenhuma nova mutação.

O M3.3 também está concluído. A DeepSeek recebe apenas o subconjunto localmente
relevante do `ToolRegistry`, limitado a quatro ferramentas e ordenado de forma
estável. O seletor obteve recall 20/20 e reduziu 57,6% dos schemas no corpus v1;
pedidos perigosos receberam somente leituras. Isso melhora velocidade e foco sem
delegar seleção a outra chamada de IA nem criar permissão nova.

O M3.4 está concluído. A IA pode pedir leituras, receber resultados estruturados
e revisar a resposta em até quatro rodadas. O usuário vê o progresso e pode
cancelar; a memória é temporária e vinculada à revisão CAD. O controlador nunca
executa mutações: ao encontrar uma, encerra a descoberta e entrega apenas a
proposta para o fluxo de confirmação já existente.

O M3.5 está concluído. Uma mutação proposta pela IA é congelada com hash e
`DocumentStateToken`; o clique autoriza somente aquele plano e aquela chamada por
um prazo curto. O executor recusa estado obsoleto, revalida tudo pelo registro,
executa uma única transação e confere a pós-condição. Alterar silenciosamente o
plano depois de exibido deixa de ser possível.

O M3.6a está concluído no chat. A IA pode propor de duas a oito mutações com uma
aprovação única; todas são pré-validadas e qualquer falha desfaz apenas as etapas
do plano, verificando a restauração da baseline. O mesmo serviço já possui status
e cancelamento idempotentes em memória. Falta projetá-lo pela ponte autenticada
para o processo MCP antes de considerar todo o M3.6 encerrado.

## Diferenciais pretendidos

- operação local e privada;
- histórico completo das ações da IA;
- mesma capacidade no chat e via MCP;
- modelos paramétricos editáveis;
- validação antes de exportar ou fabricar.
