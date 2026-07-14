# AI CAD Workbench

Base inicial de um ambiente CAD paramétrico controlável por chat interno e por MCP.

O primeiro protótipo usa o FreeCAD como motor de modelagem, visualização e documento. A camada `aicad` concentra ferramentas determinísticas, permissões e a integração local com MCP.

## Estado atual

- Workbench `AI CAD` carregável pelo ambiente portátil já preparado.
- Painel lateral com chat local determinístico e sem dependência de provedor.
- Comandos para ler documento e seleção, validar, criar caixas e cilindros e desfazer.
- Confirmação explícita na interface antes de criar ou desfazer.
- `ToolRegistry` único para catálogo, schemas, validação e política de risco.
- Chat e MCP conectados ao mesmo registro e ao mesmo adaptador.
- Caixas e cilindros criados em transações validadas e reversíveis.
- Ponte MCP–GUI autenticada, restrita ao loopback e executada pela thread Qt.
- Mutações MCP pendentes até confirmação explícita no painel.
- Base de orquestração neutra valida planos e chamadas sem executar ferramentas.
- Contrato versionado para resultados, erros seguros e métricas monotônicas do agente.
- Benchmark offline v1 com 30 pedidos em português e baseline reproduzível.
- Contexto L0/L1 versionado com documento, seleção, objetos recentes e paginação.
- Mudanças manuais relevantes alteram o token de estado e invalidam contexto antigo.
- Seletor local PT/EN envia somente ferramentas relevantes em ordem estável à IA.
- Benchmark do seletor: recall 20/20 e economia de 57,6% dos schemas no corpus v1.
- Loop DeepSeek limitado executa leituras, devolve resultados e permite cancelar.
- Memória de leitura permanece em RAM e é invalidada quando o estado CAD muda.
- Mutação da IA usa plano imutável, hash, estado-base e autorização de curta duração.
- Planos de 2–8 mutações usam aprovação única e rollback compensatório verificado.
- Testes unitários, teste transacional no FreeCADCmd e fluxo MCP gráfico automatizado.
- Instalação reproduzível e isolada para Windows.

## Preparação

Execute no PowerShell:

```powershell
.\scripts\setup.ps1
```

Se o ambiente já estiver preparado, não execute o setup novamente.

Depois, abra o FreeCAD com:

```powershell
.\scripts\iniciar.ps1
```

O ambiente `AI CAD` aparecerá na lista de Workbenches.

## Chat local

O painel aceita, nesta fase, um vocabulário fechado. Exemplos:

```text
resumo
seleção
contexto
validar
caixa 10 x 20 x 30 nome MinhaCaixa
cilindro 30 x 60 nome Eixo
desfazer
```

Leituras são executadas imediatamente. Criação e desfazer mostram o plano e só
executam depois do clique em **Confirmar operação**. Texto livre não vira Python
nem é enviado a um serviço externo.

## MCP local

Com o FreeCAD aberto por `scripts/iniciar.ps1`, o servidor MCP encontra a sessão
gráfica por um registro efêmero no diretório local do usuário. Leituras percorrem
a ponte e são executadas na thread principal do Qt. Para qualquer ferramenta
`modify`, `request_cad_tool` retorna `pending_confirmation`; somente o clique no
painel autoriza a execução.

O mesmo `request_id`, nome e argumentos podem ser reenviados para consultar o
resultado sem repetir a mutação. Reutilizar o ID com conteúdo diferente é
rejeitado.

O transporte escuta apenas em `127.0.0.1`, usa token aleatório por sessão,
mensagens limitadas e timeout. O token não é gravado no repositório nem exibido
em logs.

## IA DeepSeek

No painel do FreeCAD:

1. clique em **Configurar chave DeepSeek**;
2. cole a chave no campo mascarado e confirme;
3. marque **Usar IA DeepSeek**;
4. escreva o pedido em linguagem natural e clique em **Enviar**.

A chave fica no Gerenciador de Credenciais do Windows por meio de **keyring**.
Ela não é salva em arquivos de ambiente, arquivos do projeto, logs ou histórico
do painel. Abrir o painel não consulta o cofre. Depois de configurar ou remover,
o status mostra apenas o estado da credencial, nunca seu conteúdo.

O modo começa desligado. Marcar a opção não faz uma chamada por si só, mas cada
envio feito enquanto ela estiver marcada transmite o texto e um snapshot limitado
e versionado do documento ativo para https://api.deepseek.com/chat/completions. Um
seletor local escolhe até quatro ferramentas relevantes antes do envio, sem outra
chamada ao modelo. O adaptador usa **deepseek-v4-flash** e pode fazer até quatro
rodadas controladas para ler o documento e revisar a resposta.

Respostas de leitura podem usar o ToolRegistry imediatamente. Operações
**modify**, como criar uma caixa, um cilindro ou desfazer, mostram intenção,
plano, ferramenta, argumentos, ID, hash e revisão-base. O clique em **Confirmar
operação** autoriza somente essa chamada exata e por poucos segundos. O documento
é relido antes da execução; qualquer mudança invalida o plano. Desmarcar a opção
restaura o chat local fechado. O botão **Remover chave** apaga a credencial.

Durante uma consulta, o painel mostra se está preparando contexto, selecionando
ferramentas, consultando o modelo, validando ou lendo o documento. **Cancelar
consulta da IA** solicita interrupção cooperativa no próximo ponto seguro. As
leituras pedidas pelo modelo são executadas na thread principal do FreeCAD; seus
resultados voltam ao modelo com ID, status e código de erro controlado. O loop não
executa mutações e não repete indefinidamente.

## Testes

```powershell
.\scripts\testar.ps1
```

A suíte abre e fecha automaticamente uma instância isolada do FreeCAD para
confirmar que o Workbench aparece, o painel abre e o fluxo criar/desfazer funciona.

O benchmark offline não usa provedor, chave ou FreeCAD:

```powershell
.\scripts\benchmark_agent.ps1
```

A baseline M3.1 mede o parser local atual em 30 casos: 14 das 20 escolhas de
ferramenta são exatas, os 10 pedidos sem ferramenta são bloqueados com segurança
e ainda não há esclarecimento ou rejeição explicativa. Esses números são a régua
para contexto e seleção de ferramentas nas próximas etapas.

Para medir a recuperação local usada pelo modo DeepSeek:

```powershell
.\scripts\benchmark_agent.ps1 -Strategy selector
```

No corpus v1, o seletor recupera a ferramenta esperada em 20/20 pedidos, não
expõe mutações nos cinco pedidos perigosos, envia em média 2,83 das sete
ferramentas e reduz em 57,6% os bytes de schemas. A medição é local e não acessa
rede, chave ou FreeCAD.

## Segurança

Chaves de API nunca são salvas no repositório. O painel grava e remove a
credencial somente pelo cofre do Windows. A pasta `.runtime`, ambientes,
downloads, arquivos CAD gerados e segredos permanecem ignorados pelo Git.
Salvar uma chave não ativa o provedor automaticamente; o envio externo
depende da opção visível **Usar IA DeepSeek**.

O MCP não acessa o adaptador diretamente. Toda chamada passa pelo protocolo
tipado, pela validação do `ToolRegistry`, pela fila da GUI e, nas mutações, pela
confirmação visual.

`cad.get_context_snapshot` está no mesmo registro usado pelo chat e pelo MCP.
Ela é somente leitura, limita objetos, suporta paginação e não expõe token da
ponte, segredo ou caminho local.

O seletor não cria permissões nem executa ferramentas. Ele apenas reduz o catálogo
que a IA enxerga; nomes e argumentos retornados continuam sendo revalidados pelo
`ToolRegistry`. Pedidos reconhecidos como tentativa de Python arbitrário, comando
do sistema, macro, remoção de arquivos ou desvio de confirmação recebem somente
ferramentas de leitura.

Uma proposta de mutação DeepSeek vira `ValidatedPlan`. O hash cobre estado-base,
intenção, passos, ferramenta e argumentos. `ApprovalGrant` é criado somente no
clique, autoriza um único `call_id`, expira rapidamente e não contém segredo. O
executor confere novamente hash, autorização, schema, risco e estado, executa uma
única mutação transacional e valida o documento e o novo estado depois.

O corte M3.6a permite planos compostos no chat DeepSeek quando já existe um
documento ativo. Todas as chamadas são pré-validadas antes da primeira mutação.
Uma aprovação cobre o hash e todos os IDs; cada etapa é validada. Em falha ou
cancelamento entre etapas, somente as transações já confirmadas pelo plano são
desfeitas, e documento, seleção e fingerprint precisam voltar à baseline. `undo`
não pode ser uma etapa composta porque ainda não há compensação segura por redo.

## Arquitetura

Consulte [docs/architecture.md](docs/architecture.md),
[docs/product-vision.md](docs/product-vision.md) e
[docs/milestones.md](docs/milestones.md). O último contém o plano completo de
marcos e o roteiro para retomar o projeto em outro computador ou chat. A evolução
detalhada do loop, contexto, seleção de ferramentas, planos compostos e desempenho
está em
[docs/ai-agent-optimization-plan.md](docs/ai-agent-optimization-plan.md).
