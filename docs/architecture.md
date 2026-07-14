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

`aicad.orchestration` define o primeiro bloco do M3 sem importar FreeCAD, Qt ou
qualquer SDK de IA. O contrato `ProviderRequest` envia somente a mensagem atual,
contexto JSON limitado e as definições de ferramentas permitidas para a rodada.

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
de 30 segundos e no máximo uma ferramenta por rodada no painel.

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
painel ainda não consome esses contratos; essa integração ocorrerá com o loop do
agente, preservando o comportamento atual.

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
simples, ainda com uma única rodada e uma única ferramenta proposta. Nenhuma
permissão de mutação foi ampliada.

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
2. Um worker recupera a chave do cofre e chama o adaptador DeepSeek.
3. AiOrchestrator revalida ferramenta, argumentos, risco e limites sem executar.
4. O timer Qt recebe somente o plano validado e o apresenta com dados escapados.
5. Leituras são executadas na thread Qt pelo registro compartilhado.
6. Mutações entram no mesmo estado pendente do chat e exigem confirmação visual.
7. A execução confirmada segue para o FreeCadAdapter transacional e reversível.

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

Caixa e cilindro usam a mesma rotina transacional do adaptador:

1. validam dimensões finitas, positivas e o nome;
2. garantem que o histórico de desfazer esteja habilitado;
3. abrem uma transação nomeada;
4. criam e configuram o objeto paramétrico;
5. recalculam e validam forma e documento dentro da transação;
6. confirmam em caso de sucesso ou abortam e recalculam em qualquer falha.

O cilindro recebe diâmetro e altura em milímetros, calcula o raio localmente e
fica alinhado ao eixo Z. Os testes exigem volume correto, duas transações
independentes e remoção ordenada por `undo`.
## Fluxo atual do MCP

O servidor MCP e a GUI usam a mesma composição do registro em seus processos.
`request_cad_tool` valida a chamada, descobre a sessão gráfica e envia o envelope
para a fila pertencente à GUI.

Leituras retornam o resultado executado na thread Qt. Mutações retornam
`pending_confirmation`, aparecem no painel e só usam `confirmed=True` depois do
clique do usuário. Repetir a request com o mesmo ID consulta o resultado.

## Próxima etapa técnica

M3.1 e M3.2 foram concluídos. Seguir o M3.3 em
`docs/ai-agent-optimization-plan.md`: enriquecer metadados de `ToolSpec` e criar o
seletor local PT/EN com top-N e ordenação canônica. Depois entra o loop iterativo
somente leitura. Mutações com planos imutáveis e planos compostos continuam
bloqueadas até essas bases passarem nos critérios de aceite.
