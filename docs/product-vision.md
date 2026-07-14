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
até confirmação visual. Este primeiro corte usa somente uma rodada e uma
ferramenta, sem loop autônomo. Exportação para fabricação ainda não foi
implementada.

O M3.1 também está concluído: resultados e erros do futuro loop possuem contrato
versionado, as etapas podem ser medidas com relógio monotônico sem persistir dados
e um corpus offline de 30 pedidos registra a baseline do parser atual. Isso ainda
não muda o comportamento do painel; fornece a régua segura para o contexto
versionado do M3.2.

## Diferenciais pretendidos

- operação local e privada;
- histórico completo das ações da IA;
- mesma capacidade no chat e via MCP;
- modelos paramétricos editáveis;
- validação antes de exportar ou fabricar.
