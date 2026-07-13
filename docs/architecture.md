# Arquitetura inicial

## Princípio

A IA planeja, a camada de ferramentas autoriza, o FreeCAD executa e o validador verifica.

## Componentes

1. **Interface** — painel lateral dentro do FreeCAD.
2. **Orquestrador de IA** — futuramente usa a Responses API e outros provedores.
3. **ToolRegistry** — catálogo único, tipado e auditável de ações.
4. **FreeCadAdapter** — única camada autorizada a importar e modificar o FreeCAD.
5. **MCP** — expõe o mesmo catálogo para agentes externos.
6. **Validação** — verifica recomputação, forma, medidas e exportação.

## Regra de dependência

`aicad.core` não importa FreeCAD ou Qt. A UI, o MCP e os provedores dependem do núcleo. Somente `aicad.adapters.freecad_adapter` conversa diretamente com o FreeCAD.

## Próxima etapa técnica

Criar uma ponte local entre o servidor MCP e o processo gráfico do FreeCAD, com fila única de comandos e execução na thread principal do Qt.
