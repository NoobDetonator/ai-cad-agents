# Visão do produto

O AI CAD Workbench é um servidor MCP seguro para modelagem mecânica no FreeCAD.
O agente externo interpreta o pedido; o projeto fornece ferramentas pequenas,
validadas, reversíveis e observáveis.

## Estratégia

- MCP primeiro;
- FreeCAD como adaptador geométrico;
- um único catálogo para chat e agentes externos;
- confirmação humana visível;
- nenhuma execução de Python, macro ou shell gerado;
- operação local e auditável.

A IA interna com DeepSeek permanece opcional e em manutenção. Não haverá camada
multi-provedor dentro do Workbench: o usuário escolhe o modelo pelo agente que
conecta ao MCP.

## Público inicial

Modelagem mecânica para impressão 3D e fabricação leve: caixas, suportes,
adaptadores, flanges, placas, eixos, polias, engrenagens e peças furadas.

## Experiência desejada

1. O agente entende intenção, dimensões e referência.
2. Lê o documento e explicita suposições.
3. Propõe um plano somente com ferramentas registradas.
4. O painel aplica a política de aprovação.
5. O sistema executa, recalcula e valida.
6. O agente mede e captura o resultado.
7. A exportação exige confirmação manual.

## Diferenciais

- schemas em vez de scripts gerados;
- transações e rollback verificável;
- seleção eficiente entre 90 ferramentas;
- contexto, medidas e imagens para autocorreção;
- auditoria local com redaction;
- mesmas capacidades no painel e no MCP.

## Limites

O sistema não promete cobrir todo o FreeCAD. A baseline atual não inclui árvore
Part Design completa, superfícies avançadas, chapa, desenho técnico, CAM ou FEM.
Roscas, rolamentos e mecanismos impressos são modelos conceituais e precisam de
validação conforme material, processo, carga e tolerância reais.

## Evolução

M0 a M7 estão concluídos. Não há próximo marco automático. Novos incrementos
devem responder a casos reais e preservar catálogo único, schemas pequenos,
aprovação, transação, validação, auditoria e testes reproduzíveis.
