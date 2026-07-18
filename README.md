<p align="center">
  <img src="docs/images/logo.png" alt="TALOS — FreeCAD MCP" width="1000">
</p>

<h1 align="center">TALOS</h1>

<p align="center"><strong>FreeCAD MCP seguro, estruturado e orientado a agentes.</strong></p>

TALOS é um servidor MCP para controlar o FreeCAD com ferramentas CAD estruturadas. Agentes
como Codex, Claude Code e Cursor podem inspecionar, modelar, validar e exportar
peças sem executar Python, macros ou comandos arbitrários.

O FreeCAD é o motor geométrico. Schemas, política de risco, planos, auditoria e
regras do produto permanecem independentes dele.

## Estado atual

- FreeCAD 1.1.1 instalado no Windows;
- Workbench **TALOS MCP** com painel de ponte, capacidades, aprovações e atividade;
- 117 ferramentas no mesmo `ToolRegistry` para a ponte e o servidor MCP;
- núcleo Part Design paramétrico (P1): Body, sketches anexados aos planos de
  origem, pad/pocket/revolução/groove/padrões por reflexão governada, edição
  por cota e status de restrições do sketch;
- referências semânticas (P2): faces e arestas por papel geométrico, sketch
  em face sólida e dressups fillet/chanfro paramétricos;
- parâmetros mestres (P3): VarSet com cotas e features vinculadas por
  expressão de gramática fechada — mudar um parâmetro recalcula o modelo;
- cinco projetos canônicos provados de ponta a ponta por agente via MCP
  (placa, flange, suporte em L, case com tampa e estágio planetário), com
  baselines de telemetria versionadas em `benchmarks/`;
- validação de engenharia: massa/CG por densidade e prontidão de impressão
  3D (P5);
- modelagem básica e avançada, Sketch, montagens, rolamentos e exportação;
- mutações transacionais, validadas, auditadas e reversíveis;
- erros MCP categorizados, recuperáveis e com estado seguro explícito;
- descoberta compacta e paginada, com schemas completos somente sob demanda;
- captura multivista e vistas em corte XY/XZ/YZ com restauração do viewport;
- `inspect_cad_model` para contexto, validação, medidas e imagens em uma chamada;
- telemetria em memória para bytes/tokens estimados, bridge, GUI e confirmação;
- confirmação visível por padrão; `TALOS_AUTO_APPROVE=1` aprova automaticamente apenas mutações compensáveis, e exportações são sempre manuais.

O painel não expõe chat interno, seletor de provedor nem campo de chave. A IA
embutida foi removida: o modelo é sempre escolhido pelo agente externo que
conecta ao MCP.

### Atualizações recentes

- P1–P4 entregues: Part Design paramétrico por reflexão governada,
  referências semânticas, parâmetros mestres por expressão e a metodologia
  embutida ([plano P](docs/partdesign-roadmap.md));
- P5 e os cinco canônicos do P6 provados por agente via MCP, com sonda
  headless de frames e baselines de telemetria versionadas;
- restrições ancoram na origem e nos eixos do Sketcher (datums -1/-2);
- nome unificado: o pacote, o Workbench e o executável agora são `talos`.

## Início rápido

Com o FreeCAD 1.1 instalado, um comando prepara tudo (venv, Workbench e
configuração MCP):

```powershell
.\scripts\instalar.ps1
```

Depois:

1. Abra o FreeCAD e selecione o Workbench **TALOS MCP**.
2. Mantenha o painel aberto para publicar a ponte MCP.
3. Conecte seu agente seguindo [docs/mcp-integration.md](docs/mcp-integration.md).

O repositório já inclui `.mcp.json`. No uso diário não é necessário iniciar o
FreeCAD por script. O painel também oferece a configuração MCP pronta para copiar.

## O que o catálogo cobre

| Área | Capacidades principais |
| --- | --- |
| Contexto | documentos, seleção, medidas, massa/CG por densidade, prontidão de impressão 3D, vistas múltiplas e cortes visuais |
| Primitivas | caixa, cilindro, cone, esfera, toro e placas |
| Sketch | 24 ferramentas de geometria, restrições, cotas, edição e inspeção |
| Part Design | Body paramétrico, sketch anexado (plano ou face), pad, pocket, furos com counterbore, revolução, groove, padrões, fillet, chanfro, edição por cota e graus de liberdade |
| Features | pad, revolução, loft, sweep, furos, booleanas, filetes e chanfros |
| Repetição | espelho, padrões lineares, polares e padrões de furos |
| Mecânica | engrenagens, roscas, montagens, interferência e alinhamento |
| Rolamentos | modelos convencionais e adaptados à impressão 3D |
| Saída | salvamento `.FCStd`, exportação STL e STEP |

Use `search_cad_capabilities` para encontrar cartões compactos e
`describe_cad_capabilities` para carregar somente os schemas escolhidos.
`available_cad_tools` permanece como compatibilidade e auditoria completa.
Para verificação, `inspect_cad_model` agrupa as leituras comuns e confirma por
`DocumentStateToken` que o documento não mudou durante a inspeção.
`get_mcp_performance_snapshot` mostra métricas apenas do processo atual, sem
armazenar argumentos, nomes de arquivos ou conteúdo dos pedidos.

## Vitrine

**[Turbina Savonius de mesa](showcase/turbina-savonius/README.md)** — duas
peças, zero parafusos: rotor de três pás com rolamento print-in-place fundido
no cubo, base com pino chanfrado, folga verificada por interferência e tudo
dirigido por parâmetros mestres. Modelada inteira por um agente via MCP.

![Turbina Savonius](showcase/turbina-savonius/turbina-isometrica.png)

Outros exemplos validados: estágio planetário 60/20/20 sem interferências
entre os quatro engrenamentos e os cinco projetos canônicos do plano P, com
baselines de telemetria em `benchmarks/`.

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

A verificação local inclui Ruff, checagem de tipos do núcleo, cobertura mínima,
testes unitários, oito smokes no FreeCADCmd e o smoke gráfico do painel MCP.
A mesma base neutra roda no CI do Windows sem exigir uma instalação do FreeCAD.

A suíte cobre mais de 200 testes unitários, FreeCADCmd e a interface gráfica real. Para
medir a seleção de ferramentas sem rede ou FreeCAD:

```powershell
.\scripts\benchmark_agent.ps1
.\scripts\benchmark_agent.ps1 -Corpus benchmarks\agent-corpus-heldout-v1.json
```

Os corpora históricos verificam regressões conhecidas. O corpus `heldout` não
reutiliza frases canônicas do catálogo e mede rank-1, MRR, precisão@K,
esclarecimentos e exposição indevida de mutações. A economia de schema reportada
é teórica e assume ausência de cache no cliente MCP.

## Regras do repositório

- MCP é o produto principal; não existe IA embutida no Workbench.
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
- [Otimização do agente](docs/ai-agent-optimization-plan.md)
- [E1 — MCP em escala](docs/mcp-scale-roadmap.md)
- [P — Part Design profissional](docs/partdesign-roadmap.md)
- [Estudo do concorrente freecad-mcp](docs/estudo-freecad-mcp.md)

## Licença

LGPL-2.1-or-later, alinhada ao FreeCAD. Veja [LICENSE](LICENSE).
