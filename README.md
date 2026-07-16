# AI CAD Workbench

Servidor MCP para controlar o FreeCAD com ferramentas CAD estruturadas. Agentes
como Codex, Claude Code e Cursor podem inspecionar, modelar, validar e exportar
peças sem executar Python, macros ou comandos arbitrários.

O FreeCAD é o motor geométrico. Schemas, política de risco, planos, auditoria e
regras do produto permanecem independentes dele.

## Estado atual

- FreeCAD 1.1.1 instalado no Windows;
- Workbench **AI CAD** com painel lateral e ponte MCP local;
- 90 ferramentas no mesmo `ToolRegistry` para chat e MCP;
- M0 a M7 concluídos; E1 — MCP em escala em execução;
- modelagem básica e avançada, Sketch, montagens, rolamentos e exportação;
- mutações transacionais, validadas, auditadas e reversíveis;
- aceitação automática visível por padrão; exportações sempre manuais.

A IA interna com DeepSeek continua disponível, mas está em manutenção. O foco do
produto é o uso por agentes externos via MCP.

## Início rápido

1. Prepare a `.venv` e vincule o Workbench conforme
   [docs/installation.md](docs/installation.md).
2. Abra o FreeCAD normalmente.
3. Selecione o Workbench **AI CAD**.
4. Mantenha o painel aberto para publicar a ponte MCP.
5. Conecte seu agente seguindo [docs/mcp-integration.md](docs/mcp-integration.md).

O repositório já inclui `.mcp.json`. No uso diário não é necessário iniciar o
FreeCAD por script.

## O que o catálogo cobre

| Área | Capacidades principais |
| --- | --- |
| Contexto | documentos, seleção, objetos, medidas, dependências e captura visual |
| Primitivas | caixa, cilindro, cone, esfera, toro e placas |
| Sketch | 24 ferramentas de geometria, restrições, cotas, edição e inspeção |
| Features | pad, revolução, loft, sweep, furos, booleanas, filetes e chanfros |
| Repetição | espelho, padrões lineares, polares e padrões de furos |
| Mecânica | engrenagens, roscas, montagens, interferência e alinhamento |
| Rolamentos | modelos convencionais e adaptados à impressão 3D |
| Saída | salvamento `.FCStd`, exportação STL e STEP |

Use `search_cad_capabilities` para encontrar cartões compactos e
`describe_cad_capabilities` para carregar somente os schemas escolhidos.
`available_cad_tools` permanece como compatibilidade e auditoria completa.

## Exemplo validado

Estágio planetário 60/20/20 com dois planetas opostos, validado no FreeCAD sem interferências entre os quatro engrenamentos.

![Estágio planetário validado](docs/images/planetary-gear-demo.png)

## Fluxo seguro

1. O agente lê o documento e resolve referências.
2. Um plano usa somente ferramentas registradas.
3. O painel aplica a política de aprovação visível.
4. Cada mutação abre uma transação, recalcula e valida o documento.
5. Falhas abortam a operação; planos compostos fazem rollback verificado.
6. O agente mede ou captura o resultado antes de exportar.

Não existe ferramenta para executar código arbitrário. Chaves não são gravadas
no projeto e caminhos locais sensíveis são removidos da auditoria.

## Desenvolvimento

Instale o projeto em modo editável e execute a suíte completa antes de concluir
uma alteração:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\testar.ps1
```

A suíte cobre mais de 200 testes unitários, FreeCADCmd e a interface gráfica real. Para
medir a seleção de ferramentas sem rede ou FreeCAD:

```powershell
.\scripts\benchmark_agent.ps1 -Strategy selector
```

## Regras do repositório

- MCP é o produto principal; a IA embutida recebe apenas manutenção.
- FreeCAD permanece atrás do adaptador.
- Chat e MCP usam o mesmo `ToolRegistry`.
- Toda mutação CAD é transacional, validada e reversível.
- Nenhuma ferramenta executa Python, macro ou shell arbitrário.
- Código neutro deve continuar testável sem FreeCAD instalado.

## Documentação

- [Instalação](docs/installation.md)
- [Integração MCP](docs/mcp-integration.md)
- [Arquitetura](docs/architecture.md)
- [Ambiente de Sketch](docs/sketch-environment.md)
- [Rolamentos](docs/bearings.md)
- [Auditoria](docs/audit.md)
- [Visão do produto](docs/product-vision.md)
- [Baseline M0–M7](docs/milestones.md)
- [Otimização do agente](docs/ai-agent-optimization-plan.md)
- [E1 — MCP em escala](docs/mcp-scale-roadmap.md)
