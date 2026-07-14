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
envio feito enquanto ela estiver marcada transmite o texto e um resumo limitado
do documento ativo para https://api.deepseek.com/chat/completions. O adaptador
usa **deepseek-v4-flash** e uma rodada com no máximo uma chamada de ferramenta.

Respostas de leitura podem usar o ToolRegistry imediatamente. Operações
**modify**, como criar uma caixa, um cilindro ou desfazer, mostram intenção,
plano, ferramenta
e argumentos e só são executadas depois de **Confirmar operação**. Desmarcar a
opção restaura o chat local fechado. O botão **Remover chave** apaga a credencial.

## Testes

```powershell
.\scripts\testar.ps1
```

A suíte abre e fecha automaticamente uma instância isolada do FreeCAD para
confirmar que o Workbench aparece, o painel abre e o fluxo criar/desfazer funciona.

## Segurança

Chaves de API nunca são salvas no repositório. O painel grava e remove a
credencial somente pelo cofre do Windows. A pasta `.runtime`, ambientes,
downloads, arquivos CAD gerados e segredos permanecem ignorados pelo Git.
Salvar uma chave não ativa o provedor automaticamente; o envio externo
depende da opção visível **Usar IA DeepSeek**.

O MCP não acessa o adaptador diretamente. Toda chamada passa pelo protocolo
tipado, pela validação do `ToolRegistry`, pela fila da GUI e, nas mutações, pela
confirmação visual.

## Arquitetura

Consulte [docs/architecture.md](docs/architecture.md),
[docs/product-vision.md](docs/product-vision.md) e
[docs/milestones.md](docs/milestones.md). O último contém o plano completo de
marcos e o roteiro para retomar o projeto em outro computador ou chat.
