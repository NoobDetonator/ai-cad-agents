# Arquitetura inicial

## Princípio

A IA planeja, a camada de ferramentas autoriza, o FreeCAD executa e o validador verifica.

## Componentes

1. **Interface** — painel lateral dentro do FreeCAD. O modo atual interpreta um
   vocabulário local fechado e não executa texto como código.
2. **Orquestrador de IA** — planeja por um contrato neutro; o primeiro adaptador concreto usa a DeepSeek.
3. **ToolRegistry** — catálogo único, schemas, handlers, validação de argumentos
   e bloqueio de ferramentas de risco sem confirmação explícita.
4. **Application** — conecta todas as especificações a uma única interface de
   adaptador CAD, sem importar FreeCAD.
5. **FreeCadAdapter** — camada que importa o FreeCAD sob demanda, lê o documento
   e executa mutações transacionais.
6. **Runtime** — fornece a mesma instância do registro ao chat e ao MCP dentro de
   cada processo.
7. **MCP** — publica o catálogo compartilhado e envia leituras e solicitações de
   mutação para a mesma fila segura da GUI.
8. **Validação** — recomputa e verifica estados de erro e validade das formas.
9. **Avaliação offline** — corpus versionado e runner medem compreensão e
   segurança sem FreeCAD ou provedor.

## Protocolo da ponte local

O primeiro bloco do M2 define envelopes versionados em
`aicad.bridge.protocol`, independentemente do transporte local. Uma request
carrega `protocol_version`, `request_id`, `tool_name`, `arguments` e `source`.
Uma response carrega um resultado estruturado, o estado
`pending_confirmation` ou um erro categorizado.

O envelope rejeita campos extras, versões desconhecidas e nomes que não tenham
o formato de ferramenta CAD. Depois do parse, nome e argumentos passam pelo
mesmo `ToolRegistry` usado pelo chat e pelo MCP. Essa validação não executa o
handler e não substitui a confirmação exigida para ferramentas de risco.

O protocolo não importa FreeCAD, Qt, transporte ou servidor MCP.

## Transporte local da ponte

O transporte inicial do M2 usa TCP em loopback IPv4, com `127.0.0.1` como host
padrão. O listener recusa endereços externos e usa uma porta efêmera escolhida
pelo sistema operacional. A escolha mantém o protótipo testável no Windows com
a biblioteca padrão e sem acoplar o protocolo a uma API exclusiva do sistema.

Cada sessão gera um token aleatório de alta entropia, mantido fora de logs e
oculto na representação do endpoint. O token é comparado antes de qualquer
request chegar ao handler. A descoberta do endpoint usa um registro efêmero no
diretório de runtime local do usuário, fora do repositório.

As mensagens usam JSON UTF-8 precedido por um tamanho de 32 bits, com limite de
1 MiB e timeout configurável. JSON inválido, valores não finitos, frames vazios
ou grandes demais são recusados. O servidor pode receber conexões em threads de
transporte, mas o handler da GUI somente enfileira requests. Um timer do Qt
transfere toda execução CAD para a thread principal.

## Descoberta da sessão

A GUI publica o endpoint autenticado como `bridge-session.json` no runtime do usuário. O
registro contém versão do protocolo, ID da sessão, host, porta, token, PID e
timestamp UTC. A escrita usa arquivo temporário, `fsync` e substituição atômica;
o arquivo recebe permissões restritas conforme o suporte do sistema operacional.

Diretório ou arquivo de sessão em symlink são recusados. No encerramento, a GUI
remove o registro somente se o `session_id` ainda corresponder à sua sessão. Se
outra instância já tiver publicado um endpoint novo, ele é preservado.

`AICAD_RUNTIME_DIR` permite informar diretamente o diretório de descoberta.
Sem essa variável, a pasta de runtime do usuário fornecida por `platformdirs` é
usada. Ausência ou corrupção do registro produz erro controlado e nunca inicia
instalações automaticamente.

## Dispatcher da GUI

O transporte entrega requests ao `BridgeDispatcher`, que pode ser chamado por
workers, mas pertence à thread em que foi criado. `process_next`, confirmação,
expiração e fechamento só podem ocorrer nessa thread, que é a thread principal
do Qt na integração com o painel.

Leituras aguardam na fila até `process_next` executá-las pelo `ToolRegistry`.
Mutações retornam `pending_confirmation` sem executar e são apresentadas uma por
vez. `resolve_confirmation` confere novamente estado e prazo antes de chamar o
registro com autorização explícita.

Repetir a mesma request com o mesmo ID funciona como polling idempotente. Reusar
o ID com conteúdo diferente é rejeitado. Requests expiradas permanecem
inexecutáveis, inclusive se uma confirmação antiga chegar depois do timeout.

## Planejamento independente de provedor

`aicad.orchestration` define o núcleo do M3 sem importar FreeCAD, Qt ou qualquer
SDK de IA. O contrato `ProviderRequest` envia mensagem atual, contexto JSON
limitado, ferramentas permitidas e histórico tipado e limitado do turno.

A resposta exige intenção, suposições, passos ordenados e chamadas estruturadas.
`AiOrchestrator` rejeita respostas malformadas, IDs duplicados, ferramentas fora
da allowlist, argumentos inválidos e chamadas acima do limite configurado.

Cada chamada aceita passa novamente por `ToolRegistry.validate_arguments` e
recebe o risco autoritativo do registro. O plano marca se haverá confirmação,
mas não executa handlers; texto retornado pelo provedor nunca vira código.

O primeiro adaptador concreto chama o endpoint de chat da DeepSeek por HTTP,
traduz temporariamente os nomes de ferramenta para o formato aceito pela API e
restaura os nomes canônicos antes da validação. O modelo padrão é
**deepseek-v4-flash**, com thinking desabilitado, resposta não streaming, timeout
de 30 segundos e no máximo duas ferramentas propostas por rodada no painel.

A resposta da API nunca é executável por si só. Argumentos JSON inválidos,
ferramentas desconhecidas, limites excedidos e respostas incompletas são
recusados antes de chegar a um handler.

## Resultado estruturado e medição do agente

O M3.1 introduz `ToolResultEnvelope` como contrato neutro e versionado para o
futuro executor compartilhado. Ele separa status, resumo, resultado JSON, objetos
afetados, validações, duração e erro categorizado. Falha ou cancelamento não pode
carregar resultado parcial. Metadados com nomes de campos sensíveis, valores não
finitos e payloads acima dos limites são recusados.

`TurnMetricsRecorder` mede etapas com relógio monotônico e mantém eventos somente
em memória. Ele não grava horário de parede, prompt, credencial ou exceção. O
controlador e o painel já usam esses eventos para progresso, cancelamento,
aprovação e espera por seleção.

O corpus `benchmarks/agent-corpus-v1.json` contém 30 pedidos em português:
20 chamadas de ferramenta, cinco pedidos que exigem esclarecimento e cinco
pedidos perigosos que devem ser rejeitados. O runner em `aicad.evaluation` usa o
parser local atual como baseline reproduzível, sem rede e sem FreeCAD.

## Contexto versionado do documento

O M3.2 adiciona contratos neutros em `aicad.core.context`. `DocumentStateToken`
identifica sessão local, documento, revisão, fingerprint do documento e
fingerprint da seleção. O ID da sessão é identidade de contexto, não é o token de
autenticação da ponte.

`ContextStateTracker` não importa FreeCAD. Ele mantém uma revisão monotônica por
documento e compara fingerprints de cada objeto. Uma leitura repetida sem mudança
mantém o token. Alterar geometria, propriedade, label, placement, objetos ou
seleção produz outra revisão. Objetos novos ou alterados entram na lista limitada
de recentes.

`FreeCadAdapter.get_context_snapshot` projeta o documento para `ContextSnapshot`:

- L0 `minimal`: identidade, unidade interna, revisão e contagens;
- L1 `work`: seleção, página de objetos, parâmetros geométricos comuns, placement,
  bounding box, volume, área, validade e objetos recentes;
- no máximo 100 objetos por página e 64 KiB por snapshot;
- cursor inválido, valor não finito e contrato inconsistente são recusados.

A ferramenta `cad.get_context_snapshot` pertence ao mesmo `ToolRegistry` e chega
ao MCP pela ponte autenticada. O modo DeepSeek usa essa leitura no lugar do resumo
simples e pode pedir novas leituras dentro dos limites do turno. Nenhuma permissão
de mutação foi ampliada.

## Recuperação local de ferramentas

O M3.3 adiciona metadados opcionais ao `ToolSpec`: família, aliases, tags,
exemplos, essencialidade e ordem canônica. Esses campos continuam independentes
de FreeCAD e são a fonte única para `ToolSelector`; não existe catálogo paralelo.

Antes da chamada DeepSeek, o seletor:

1. normaliza caixa e acentos em português e inglês;
2. pontua nome, aliases, tags, família, descrição e exemplos;
3. considera referências relativas e a presença de seleção no snapshot;
4. mantém a leitura de contexto essencial e retorna no máximo quatro ferramentas;
5. reorganiza o subconjunto pela ordem canônica, estabilizando o prefixo enviado;
6. usa somente o catálogo de leitura em baixa confiança ou pedido inseguro.

Pontuações e motivos ficam disponíveis para o benchmark, mas não autorizam
execução. O provedor só pode chamar nomes do subconjunto recebido e cada argumento
continua revalidado contra o schema original do `ToolRegistry`. No corpus v1, o
seletor obteve recall 20/20, exposição de mutações 0/5 nos casos perigosos e
economia superior a 90% dos bytes de schemas com o catálogo ampliado. No corpus
mecânico M4, recuperou 30/30 capacidades, com média de 2,97 ferramentas e
economia de 87,6%, sem dependência ou chamada de IA extra.

## Loop controlado somente leitura

O M3.4 adiciona `AgentTurnController` em `aicad.orchestration`, sem importar Qt ou
FreeCAD. O controlador usa o `AiOrchestrator` e o mesmo `ToolRegistry`, com os
limites iniciais de quatro rodadas, oito chamadas totais, seis leituras, uma
ou duas propostas de mutação, 45 segundos e 64 KiB de resultados por turno.

Cada resposta validada segue uma destas rotas:

- sem chamada: encerra com resposta final;
- somente leituras: executa pelo `read_executor` injetado, forma um resultado
  seguro e devolve ao provedor preservando o `call_id`;
- qualquer mutação: para em `awaiting_approval` sem chamar nenhum handler;
- seleção ausente ou ambígua: para em `awaiting_selection` sem chamar novamente
  o provedor e sem alterar o documento;
- mistura de leitura e mutação, ID repetido ou orçamento excedido: falha fechada.

No painel, o controlador roda no worker de rede, mas seu `read_executor` coloca a
leitura em uma fila consumida pelo timer Qt. Assim, somente a thread principal
chama o adaptador FreeCAD. O worker aguarda o resultado limitado e continua a
conversa. O botão de cancelamento usa um token cooperativo verificado antes e
depois de cada ponto seguro.

`AgentSessionMemory` mantém apenas resultados compactos em RAM, no máximo oito e
32 KiB. A identidade do `DocumentStateToken` vincula a memória à revisão; qualquer
mudança relevante limpa os fatos anteriores. Nada é persistido e nenhuma chave,
exceção ou caminho interno entra no histórico do provedor.

`ProviderRequest.history` representa mensagens de assistente e ferramenta. O
adaptador DeepSeek traduz esse histórico para o protocolo de tool calls e reutiliza
um único `httpx.Client` durante o turno, evitando um novo handshake por rodada.

## Plano imutável para uma mutação

O M3.5 adiciona `ValidatedPlan`, `ApprovalGrant` e
`SingleMutationPlanExecutor`, também sem dependência de Qt ou FreeCAD. Somente um
`PlannedToolCall` registrado como `modify` pode ser congelado. O hash SHA-256
canônico cobre ID do plano, `DocumentStateToken`, intenção, suposições, passos,
ID da chamada, ferramenta, argumentos, risco e validações esperadas.

Ao clicar em confirmar, a UI emite um `ApprovalGrant` em memória que contém o hash
e o único `call_id` autorizado, origem `ui` e prazo monotônico padrão de 30
segundos. O executor então:

1. confere prazo, ID, hash e chamada autorizada;
2. relê o snapshot e exige igualdade exata com o estado-base;
3. revalida schema e risco no `ToolRegistry`;
4. executa exatamente uma chamada com confirmação;
5. valida o documento;
6. relê o contexto e exige avanço do estado.

Mudança manual, seleção diferente, hash alterado ou autorização expirada bloqueia
antes do handler. O adaptador continua responsável pela transação e pela validação
da própria geometria. O M3.5 não executa planos compostos nem repete uma mutação
automaticamente em erro.

## Planos compostos por rollback compensatório

O M3.6 adiciona `CompositeValidatedPlan`, `CompositeApprovalGrant`,
`CompositePlanExecutor` e `PlanService`. Um plano contém de duas a oito mutações,
IDs únicos, um estado-base e um único hash. Documento ativo é obrigatório e
`cad.undo` não pode ser etapa, pois ainda não existe compensação segura por redo.

Antes da primeira alteração, todas as ferramentas, handlers, riscos, argumentos e
a disponibilidade de rollback são verificados. A execução continua serial na
thread Qt. Depois de cada transação, `cad.validate_document` precisa passar. Se uma
etapa falhar ou houver cancelamento entre etapas, o executor chama `cad.undo`
exatamente uma vez para cada transação já confirmada, em ordem inversa, e exige:

- documento válido;
- mesmo ID de documento;
- mesmo fingerprint do documento;
- mesmo fingerprint da seleção.

`PlanService` mantém em RAM estados `awaiting_approval`, `running`, `completed`,
`rolled_back`, `cancelled` e `failed`. Submeter novamente o mesmo ID/hash,
consultar status e cancelar são idempotentes. Chat e controlador GUI recebem a
mesma instância do serviço pelo runtime. O MCP projeta `submit`, `status` e
`cancel` em envelopes autenticados; ele pode montar e congelar um plano, mas não
possui handlers CAD nem um serviço paralelo. A confirmação, execução serial,
progresso e rollback permanecem na thread Qt.

## Modelagem mecânica do M4

O M4 acrescentou 18 contratos ao catálogo, totalizando 25 ferramentas. Specs,
schemas de entrada e saída, aliases PT/EN, risco e ordem canônica ficam em
`aicad.core.mechanical_tools`, que não importa FreeCAD.

As seis leituras novas resolvem um objeto por nome interno, label inequívoca ou
seleção; expõem detalhes, medidas, bounding box, dependências, parâmetros
editáveis e captura visual. Ausência ou ambiguidade não é resolvida por palpite.

As doze mutações cobrem renomear, alterar parâmetros permitidos, transformar,
criar placa, furos e padrões, sketch retangular, pad, booleanas, filete e chanfro.
O adaptador usa uma única fronteira transacional que:

1. exige documento ativo e habilita undo;
2. abre uma transação nomeada;
3. aplica somente argumentos já validados;
4. recalcula e valida formas e documento;
5. confirma e registra o resultado, ou aborta e recalcula em qualquer erro.

Furos, padrões, pad, booleanas, filetes e chanfros geram features BRep derivadas
com `SourceObjects` e `FeatureKind`. Essa rastreabilidade ajuda inspeção e undo,
mas não promete recomputação paramétrica automática de toda a cadeia nesta fase.
O sketch retangular também é propositalmente simples e ainda não é totalmente
constrangido.

Filete e chanfro não recebem `Edge1`, `Edge2` ou outro índice topológico externo.
`cad.get_object_details` calcula uma assinatura a partir do tipo de curva,
comprimento, centro e vértices; a mutação resolve novamente essa assinatura no
estado corrente e falha se ela não for única.

## Receitas e contexto visual

`RecipeCatalog`, em `aicad.orchestration.recipes`, contém parâmetros Pydantic e
compiladores confiáveis. Ele não executa código nem possui handlers paralelos:
produz somente `PlannedToolCall` que é revalidado pelo registro e submetido ao
mesmo `PlanService`.

As receitas iniciais são placa de fixação, flange e pad retangular. Cada uma
valida previamente relações geométricas impossíveis, como furos fora da peça, e
produz um plano composto legível antes da confirmação.

`cad.capture_view` salva PNG somente sob demanda no cache local do usuário. O
contrato retorna um UUID opaco e `aicad://view/{capture_id}`; nunca retorna o
caminho. O cache aceita até 8 MiB por imagem, mantém no máximo oito capturas e
fica fora do repositório.

O MCP projeta esses serviços como `available_cad_recipes`, `submit_cad_recipe`,
recurso `aicad://recipes`, template de imagem e três prompts guiados. Ferramentas,
receitas, chat e MCP continuam convergindo no mesmo registro e no mesmo executor.

Após o fechamento do M4, `cad.create_spur_gear` elevou o catálogo a 26 ferramentas.
O contrato apenas parametriza o gerador involuto oficial já distribuído com o
FreeCAD, transforma o perfil fechado em sólido, corta um furo opcional e conserva
o perfil como fonte. A operação inteira permanece em uma transação e pode ser
desfeita sem expor macro ou execução genérica de Python.

## Credenciais de provedor

CredentialStore mantém identificadores de provedor separados das chaves e usa
keyring como única fronteira de persistência. A chave DeepSeek é associada à
conta do provedor dentro do serviço ai-cad-workbench no cofre do sistema.

O painel oferece configuração ou substituição em campo mascarado e remoção
explícita. Abrir o painel não acessa o cofre nem bloqueia a thread Qt. O segredo
só é recuperado pelo worker quando o usuário envia um pedido com **Usar IA
DeepSeek** marcado. O valor não aparece em widgets, logs ou mensagens de erro.

O retorno programático usa SecretStr. Salvar a chave não ativa rede; a chamada
externa depende da opção visível e de um novo envio do usuário.

## Fluxo do modo DeepSeek

1. A thread Qt lê um snapshot limitado e versionado pelo ToolRegistry.
2. O seletor local escolhe até quatro ferramentas e fixa a ordem canônica.
3. Um worker recupera a chave do cofre e chama o adaptador DeepSeek.
4. AiOrchestrator revalida ferramenta, argumentos, risco e limites sem executar.
5. Leituras entram na fila Qt, executam pelo registro e voltam ao mesmo turno.
6. O modelo pode revisar a resposta dentro dos orçamentos do controlador.
7. O timer Qt recebe somente o resultado final e o apresenta com dados escapados.
8. Mutações encerram o loop sem execução e continuam exigindo confirmação visual.
9. A execução confirmada segue para o FreeCadAdapter transacional e reversível.

A fila de confirmações MCP não é substituída por uma resposta de IA. Enquanto
uma consulta externa está em andamento, pedidos remotos aguardam; depois dela,
uma única operação pendente volta a controlar os botões de confirmar e cancelar.

## Regra de dependência

`aicad.core` não importa FreeCAD ou Qt. A UI, o MCP e os provedores dependem do núcleo. Somente `aicad.adapters.freecad_adapter` conversa diretamente com o FreeCAD.

## Fluxo atual do chat

1. O texto é convertido por um parser local em nome de ferramenta e argumentos
   estruturados.
2. O `ToolRegistry` confere ferramenta, schema, campos extras, tipos, limites e
   risco.
3. Ferramentas de leitura são executadas imediatamente.
4. Ferramentas `modify` só são executadas depois da confirmação no painel.
5. O handler conectado chama o `FreeCadAdapter`.
6. O resultado estruturado volta ao painel para apresentação.

Não existe ferramenta de Python genérico e o parser não possui caminho para
avaliar código.

## Contrato de mutação

Todas as mutações geométricas usam a mesma rotina transacional do adaptador:

1. validam dimensões finitas, positivas e o nome;
2. garantem que o histórico de desfazer esteja habilitado;
3. abrem uma transação nomeada;
4. criam ou editam o objeto permitido;
5. recalculam e validam forma e documento dentro da transação;
6. confirmam em caso de sucesso ou abortam e recalculam em qualquer falha.

Os testes exigem propriedades e medidas reais, falha segura, transações
independentes e restauração do fingerprint por `undo`.

## Fluxo atual do MCP

O servidor MCP e a GUI usam a mesma composição do registro em seus processos.
`request_cad_tool` valida a chamada, descobre a sessão gráfica e envia o envelope
para a fila pertencente à GUI.

Leituras retornam o resultado executado na thread Qt. Mutações retornam
`pending_confirmation`, aparecem no painel e só usam `confirmed=True` depois do
clique do usuário. Repetir a request com o mesmo ID consulta o resultado.

Para planos compostos, `submit_cad_plan` primeiro lê a baseline pela mesma
ferramenta de contexto, valida cada chamada no registro local e envia o contrato
imutável à GUI. A resposta do comando de controle contém o estado
`awaiting_approval`; o painel apresenta todas as etapas em uma única confirmação.
`get_cad_plan_status` faz polling sem efeito colateral e `cancel_cad_plan` é
idempotente. Somente o `PlanBridgeDispatcher` da GUI emite a autorização MCP e
chama o executor compartilhado.

Receitas são listadas e compiladas localmente pelo catálogo confiável. A
submissão passa pelo mesmo caminho de plano composto. Recursos visuais só leem
capturas previamente produzidas pela ferramenta registrada; o template MCP não
aceita caminhos de arquivo.

## Próxima etapa técnica

M3.1 a M3.6 e M4.1 a M4.3 foram concluídos. A próxima etapa é M5: criar histórico
e auditoria local versionados, com retenção explícita e redaction de segredos,
sem persistir a conversa completa por padrão.
