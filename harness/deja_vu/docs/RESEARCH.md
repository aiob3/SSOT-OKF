# Épico de Pesquisa — Interface do Operador, Memória e Orquestração Multiagente

## Registro

- **Status:** visão de produto reposicionada; provas de conceito ainda não autorizadas
- **Corte da pesquisa:** 30 de julho de 2026
- **Responsável pela direção:** operador
- **Natureza:** visão inicial autocontida para uma interface operável sobre o plano documental existente
- **Alvos avaliados:** seis projetos
- **Escopo estratégico ativo:** Traycer como plano documental; Kandev como candidato/referência de interface; `deja-vu` como plano de evidência; `i-have-adhd` como referência comportamental
- **Retirados do escopo ativo:** Temporal, NPCPy e JCode; preservados apenas como pontos de análise histórica
- **Mutação realizada durante a pesquisa:** nenhuma instalação, clone ou alteração de configuração

> Este épico registra uma avaliação. Sua ratificação não autoriza instalação, integração, exposição de serviços, indexação de históricos ou execução de agentes. Cada ação permanece sujeita a gate explícito do operador.

---

## 1. Resumo do épico

### Problema

O ambiente local utiliza vários agentes, harnesses e interfaces, cada um com sua própria persistência, instruções e histórico. Isso torna difícil:

- oferecer ao operador uma visão única do trabalho documentado no Traycer sem duplicar seu domínio;
- localizar onde uma decisão ou solução já apareceu;
- referenciar memórias e sessões de outro agente;
- recapitular instruções depois de compactação ou troca de interface;
- revalidar uma instrução antes de promovê-la novamente;
- oferecer essas capacidades como ferramentas consultáveis pelos próprios agentes;
- separar documentação, memória histórica, instrução canônica, interface e execução.

### Sistemas afetados

- Hermes;
- Codex direto e Codex via Traycer;
- Traycer;
- Claude Code direto e Claude Code via Traycer;
- Claude Desktop;
- Claude Design;
- Claude Web/extensão;
- Copilot CLI e, com limites, superfícies Copilot de IDE/Web.

### Resultado esperado

Estabelecer uma composição mínima em que:

1. o Traycer permaneça como plano documental de épicos, requisitos, tickets, handoffs e contexto;
2. uma interface orientada ao operador — usando Kandev como candidato ou referência — apresente esse plano sem substituí-lo;
3. instruções vigentes permaneçam em fontes versionadas e explícitas;
4. memória pessoal e sistêmica curada permaneça no Hermes;
5. históricos de múltiplos agentes possam ser pesquisados pelo Deja sem virarem verdade canônica;
6. promoção documental e dispatch exijam gates explícitos e separados do operador.

### Fora do escopo deste épico

- substituir Hermes, Traycer, Claude Code ou Codex;
- reproduzir no Kandev o domínio documental já mantido pelo Traycer;
- escolher entre “Traycer ou Kandev” como produtos concorrentes;
- importar automaticamente todo histórico local;
- promover instruções históricas sem revisão;
- incluir Temporal, NPCPy ou JCode na estratégia ativa;
- expor Kandev ou qualquer MCP sem autenticação e política explícita;
- construir adapters proprietários antes de testar protocolos já existentes;
- tratar memória recuperada como autorização de dispatch ou mutação.

---

## 2. Veredito executivo

A estratégia não é `Kandev contra Traycer`. O Traycer permanece como motor e plano documental. O Kandev é candidato ou referência de Front End para o operador: visualiza o estado documentado, prepara uma ação, mostra seu binding e somente então oferece dispatch explícito aos runtimes. O Deja fornece evidência histórica transversal; `i-have-adhd` informa a apresentação. Temporal, NPCPy e JCode não participam da estratégia ativa.

| Ordem | Componente | Papel no escopo ativo | Decisão atual |
|---|---|---|---|
| 1 | Traycer | Fonte documental de épicos, requisitos, tickets e handoffs | Preservar como plano autoritativo |
| 2 | Kandev/interface | Candidato ou referência de interface operável sobre o Traycer | Avaliar a superfície, não substituir o domínio |
| 3 | `deja-vu` | Busca e recall sobre históricos locais | Recomendar PoC isolada; adoção não decidida |
| 4 | `i-have-adhd` | Referência comportamental e de apresentação | Validar regras opt-in |

Temporal, NPCPy e JCode permanecem registrados como alternativas já analisadas, sem PoC, dependência ou consequência arquitetural neste épico.

Visão recomendada, com planos independentes e gates explícitos:

```text
                           ┌────────────────────────────────────┐
                           │ Interface do operador              │
                           │ Kandev ou Front End adaptado       │
                           │ visualizar → preview → dispatch    │
                           └──────────────┬─────────────────────┘
                                          │ lê, sem substituir
                                          ▼
┌──────────────────────────┐   ┌────────────────────────────────┐
│ Evidência histórica      │   │ Plano documental              │
│ Hermes session_search    │   │ Traycer                       │
│ + deja-vu                │   │ épicos/requisitos/tickets      │
└────────────┬─────────────┘   └────────────────────────────────┘
             │ consulta                       ▲
             └──────────────┐                 │ promoção aprovada
                            ▼                 │
                     [GATE DO OPERADOR]
                   scope → config → binding → dispatch
                            │
                            ▼
                Hermes / Claude Code / Codex
                            │ resultado
                            ▼
                     revisão do operador

AGENTS.md / CLAUDE.md / Skills = instrução canônica versionada
Hermes memory                 = fatos duráveis curados
```

---

## 3. Evidência do ambiente local

O inventário foi conduzido em modo read-only e sem leitura de segredos.

| Superfície | Estado observado |
|---|---|
| Hermes | `0.19.0`; 162 sessões, 36.198 mensagens; `state.db` com 866,2 MiB e FTS nativo |
| Codex | `0.146.0`; 248 arquivos JSONL, 423,8 MiB |
| Traycer | `1.1.9`; SQLite próprio, handoffs, shared context e retomada de sessões |
| Claude Code | `2.1.220`; 1.867 arquivos JSONL, 1,1 GiB |
| Claude Desktop | `0.12.82`; histórico portátil independente não verificado |
| Copilot CLI | `1.0.76-5`; 60 sessões, 79,8 MiB |
| Instruções locais | 60 `AGENTS.md`, 91 `CLAUDE.md`, 2 `copilot-instructions.md` |

Existem pelo menos 2.175 arquivos de sessão de Codex, Claude Code e Copilot, ocupando aproximadamente 1,6 GiB. A necessidade de recuperação transversal é, portanto, concreta.

O Hermes já resolve busca nas próprias sessões por `session_search` sobre seu banco FTS. A lacuna é a recuperação transversal sobre Claude Code, Codex, Copilot e outros harnesses.

Observações operacionais:

- Codex, Copilot e Traycer estão instalados em caminhos absolutos, mas não estavam no `PATH` normal inspecionado;
- isso afeta descoberta por control planes como Kandev, mas não impede o Deja de ler os stores;
- Claude Desktop, Claude Design e Claude Web não apresentam um store local portátil equivalente aos logs do Claude Code;
- Claude Design foi tratado como camada de skill/interface, não como memory store independente.

---

## 4. Avaliação detalhada

### 4.1 `vshulcz/deja-vu`

#### Papel correto

Plano local de busca, recall e referência entre históricos existentes de agentes. Não é orquestrador nem sistema de validação semântica.

Snapshot principal auditado: [`29910d5`](https://github.com/vshulcz/deja-vu/tree/29910d5783471a528d12342f006bb901bf797c2c). Release observada: [`v0.16.4`](https://github.com/vshulcz/deja-vu/releases/tag/v0.16.4), publicada em 30/07/2026. Licença MIT.

#### Capacidades relevantes

- descobre e indexa retrospectivamente históricos de 17 harnesses;
- inclui Claude Code, Codex, Hermes e Copilot CLI;
- busca lexical incremental com BM25, proximidade, título, atualidade e outros sinais;
- embeddings são opcionais por sidecar local;
- expõe MCP por stdio/JSON-RPC com tools como `recall`, `recall_context`, `blame` e `remember`;
- expõe recursos `deja://session/...`;
- possui hooks de auto-recall e recuperação após compactação;
- permite marcar conhecimento como `rejected`, `superseded` ou `stale`;
- possui trust policy, exclusions e redaction anterior à indexação;
- apresenta resultados recuperados como dados históricos não confiáveis;
- fornece checksum, assinatura e SBOM de release.

#### Persistência

Os históricos originais são lidos sem modificação, mas o Deja não é integralmente read-only. Ele escreve:

- índice derivado e reconstruível;
- notas locais;
- auditoria de recall;
- sidecars e embeddings opcionais;
- hooks e estado de integração;
- memórias criadas por `remember`.

O MCP inclui a tool de escrita `remember`. Um perfil estritamente read-only precisa filtrar essa tool ou bloquear a escrita por policy/filesystem.

#### Segurança

Pontos positivos:

- MCP por stdio, sem porta de rede;
- redaction de chaves, JWTs, URLs com credenciais e chaves privadas;
- políticas de confiança e exclusão por origem/projeto;
- framing de resultados como histórico não confiável para mitigar prompt injection persistente.

Limites:

- índice e sidecars não são criptografados em repouso;
- qualquer processo capaz de ler o cache pode ler o conteúdo derivado;
- redaction é heurístico, não prova ausência de segredo;
- os segredos permanecem nos históricos originais;
- existe issue recente sobre Unicode corrompido, exigindo teste em português brasileiro, nomes e caminhos Unicode.

#### Compatibilidade

| Interface | Resultado |
|---|---|
| Hermes | Suporte direto a `~/.hermes/state.db`, stores antigos por perfil, plugin e MCP |
| Codex direto | Suporte a rollouts e histórico |
| Codex via Traycer | Pode capturar o log produzido pelo Codex, sem preservar Traycer como origem própria |
| Claude Code direto | Parser JSONL, hooks, plugin e MCP |
| Claude Code via Traycer | Pode capturar sessões do CLI padrão; não conhece o domínio interno do Traycer |
| Traycer | Sem parser para SQLite/shared memory do Traycer |
| Claude Desktop | Pode consumir MCP; histórico do Desktop não é ingerido |
| Claude Design/Web | Sem parser ou integração comprovada como fonte |
| Copilot | Suporte ao Copilot CLI, não ao store completo da extensão VS Code/Web |

#### Limitação específica encontrada no Hermes local

O parser Hermes do Deja lê `messages` e classifica sessões pelo perfil. O Hermes `0.19.0` instalado possui `sessions.cwd` e `sessions.git_repo_root`, mas o parser não faz join com essa tabela e afirma incorretamente que Hermes não armazena working directory.

Consequência:

- busca transversal funciona;
- agrupamento das sessões Hermes por projeto fica degradado;
- auto-recall contextual por projeto não deve ser ativado antes de corrigir ou aceitar formalmente essa limitação.

#### O que não resolve

- não orquestra agentes;
- não cria filas, worktrees, tarefas, gates ou sessões concorrentes;
- não verifica se uma memória é verdadeira;
- não revalida automaticamente `AGENTS.md`, `CLAUDE.md` ou system prompts;
- não transforma histórico em instrução canônica;
- não integra diretamente Traycer, Kandev, Claude Web/Design/Desktop ou Copilot Chat do VS Code.

#### Veredito

**ADERENTE.** É o melhor encaixe para busca, referência e reuso de memória entre agentes, especialmente pelo Hermes. Deve ser usado como plano de evidência histórica, não como fonte normativa.

---

### 4.2 `kdlbs/kandev`

#### Papel correto

No produto deste épico, Kandev é candidato ou referência de interface para o operador. Sua função é projetar o estado documental do Traycer, permitir consulta de evidência, preparar um dispatch e apresentar resultados. Ele não substitui o Traycer nem se torna a fonte de verdade de épicos, requisitos ou tickets.

Snapshot auditado: [`3760f12`](https://github.com/kdlbs/kandev/tree/3760f12939f50b0a67b7ca48b2fd9d81e5aa12a8), sem alteração central até `b082d5e`. Release observada: [`v0.82.0`](https://github.com/kdlbs/kandev/releases/tag/v0.82.0), publicada em 25/07/2026. Licença AGPL-3.0.

#### Capacidades

As capacidades abaixo justificam avaliar sua superfície de interação, não adotar automaticamente todo o backend:

- kanban, tarefas e workflows;
- sessões paralelas e subtarefas;
- worktrees e executores locais, Docker, SSH e cloud;
- diffs, comentários, revisão, terminal, editor, Git e PRs;
- suporte a Claude Code, Codex e Copilot por ACP/bridges ou passthrough;
- HTTP/WebSocket para backend e UI;
- MCP task-scoped, Office-scoped, de terceiros e endpoint externo;
- operações de spawn, mensagens, leitura de conversa e handoff;
- persistência em SQLite por padrão, com PostgreSQL opcional.

#### Memória e instruções

Kandev possui três mecanismos próprios, mas nenhum deve virar plano documental ou memory plane canônico neste épico:

1. histórico persistido de tarefas e sessões conhecidas;
2. handover/resumo para nova sessão;
3. Office memory por workspace e tipo `agent/project/task/skill`.

Limites:

- Office está desabilitado por padrão e marcado `In progress`;
- Office memory é lookup/list por chave e camada, não busca lexical ou semântica cross-session;
- recuperar uma conversa conhecida não responde “onde já resolvemos X?”;
- `AGENTS.md` é injetado em sessão fresca, mas resume pressupõe que a CLI reteve a instrução;
- não há comparação de hash/frescura nem revalidação automática da instrução;
- continuação/resumo ainda possui caminhos parcialmente não conectados;
- duplicar épicos, tickets ou status do Traycer no store do Kandev criaria duas autoridades e está fora do escopo.

#### Segurança

A documentação declara explicitamente:

- ausência de login multiusuário, RBAC ou authorization boundary para WebUI, HTTP, WebSocket e MCP externo;
- backend padrão em `0.0.0.0`;
- MCP externo sem autenticação própria do Kandev;
- qualquer pessoa capaz de alcançar o backend deve ser tratada como operadora;
- worktree isola checkout Git, não processo, rede, credenciais ou filesystem;
- policy MCP pode partir de baseline allow-all;
- headers/env MCP podem aparecer nos argumentos do processo;
- alguns agentes podem deixar configuração MCP/credenciais em arquivos do projeto.

Condições mínimas para PoC:

```text
loopback ou VPN/proxy autenticado
conta de sistema dedicada
policy MCP explícita
nenhuma exposição direta à LAN/Internet
auto-approve desligado
sem segredos remotos desnecessários
```

#### Compatibilidade

- Claude Code, Codex e Copilot CLI: integração nativa;
- Hermes: MCP externo ou custom TUI/passthrough; sem registry nativo;
- Traycer: sem integração explícita pronta; a adaptação necessária é uma projeção read-only dos artefatos documentais e um retorno de resultados sujeito a revisão, não uma migração de domínio;
- Claude Desktop: pode atuar como cliente MCP manual, não como runtime executável;
- Claude Web/Design: sem integração comprovada.

#### Divisão de responsabilidades

```text
Traycer
- mantém épicos, requisitos, tickets, handoffs e contexto
- determina o que está documentado, pendente ou aprovado

Interface do operador inspirada no Kandev
- projeta o estado do Traycer sem duplicá-lo
- mostra capacidade, alvo, configuração e binding
- oferece preview do dispatch
- exige confirmação explícita para executar
- apresenta runtime, sessão, resultado e evidência

Hermes / Claude Code / Codex
- executam somente após o gate de dispatch
- preservam suas interfaces CLI/TUI nativas

Deja/Hermes session_search
- fornecem evidência histórica consultiva
- nunca autorizam execução ou promoção documental
```

O limite arquitetural é simples: o Front End pode ler e projetar o Traycer, mas não pode criar uma segunda verdade documental. Resultados retornam primeiro ao operador; somente uma promoção aprovada altera o plano documental.

#### Veredito

**ADERENTE COM ADAPTAÇÃO** como candidato ou referência de interface operável. Aderência não significa adoção do control plane completo. A PoC deve provar projeção do Traycer, gates e retorno de resultado sem duplicação de autoridade.

---

### 4.3 `ayghri/i-have-adhd`

#### Papel correto

Skill textual para moldar a apresentação e autonomia da resposta. Não é memória, runtime ou agente.

Snapshot auditado: [`07684c4`](https://github.com/ayghri/i-have-adhd/commit/07684c4ab625dd7d1ea6e99e065f60bc0ac6a1ba). Licença MIT; manifests ainda em `0.1.0`, sem release/tag publicado no corte.

#### Capacidades

- próxima ação na primeira linha;
- passos numerados;
- estado e progresso visíveis;
- supressão de tangentes;
- limites de lista;
- tom objetivo para erros;
- prioridade da tarefa quando uma regra de apresentação conflita com o trabalho;
- empacotamento para Claude Code, Codex, ecossistema `.agents`, Gemini e cópia para Cursor.

#### Limites

- não armazena fatos, sessões ou conversas;
- não implementa índice, busca, embeddings, banco ou grafo;
- não possui MCP ou API de ferramenta;
- não coordena agentes;
- reafirmar estado é um comportamento solicitado ao LLM, não recuperação de memória;
- o pre-send check é prompt, não validador determinístico;
- há issue reconhecendo diluição das instruções em contextos longos e necessidade de reinvocação;
- não é mecanismo confiável de revalidação pós-compactação.

#### Aderência local

Há forte sobreposição com Ponytail e Caveman. Os elementos adicionais de maior valor são:

1. restatar estado entre turnos;
2. deixar a próxima ação visível;
3. separar claramente feito de pendente.

#### Veredito

**ADERENTE COM ADAPTAÇÃO** como skill opt-in. Reaproveitar regras selecionadas é suficiente; não deve ser tratado como memory plane.

---

### 4.4 Alvos analisados e retirados do escopo ativo

Os projetos abaixo permanecem registrados para preservar a evidência da pesquisa, mas não participam da estratégia, arquitetura, PoCs ou próximos gates deste épico:

- **NPCPy:** framework agentic amplo, porém adiciona outro runtime, outro modelo de memória e uma superfície insegura sem hardening. Não será integrado nem usado como referência de implementação nesta etapa.
- **Temporal:** plataforma de durable execution madura, mas resolve um requisito que não pertence ao problema atual de memória, instruções e orquestração local. Não haverá desenho de Workflow, Worker ou Web UI neste escopo.
- **JCode:** harness local com memória híbrida real, mas introduziria outra interface e outro store sem resolver a recuperação transversal já coberta pelo Deja. Não haverá PoC ou adapter neste escopo.

Retomar qualquer um desses projetos exige uma nova decisão de escopo, motivada por requisito que não seja atendido por Hermes, Deja, Traycer/Kandev e skills existentes.

---

## 5. Matriz pelas interfaces em uso

| Interface | Caminho recomendado |
|---|---|
| Hermes | Manter `memory` + `session_search`; acrescentar Deja para outros harnesses |
| Codex direto | Deja para histórico; `AGENTS.md`/skills para instrução |
| Codex via Traycer | Deja encontra logs do Codex, mas não o contexto interno do Traycer |
| Traycer | Preservar como plano documental; projetar seus épicos, tickets e handoffs na interface do operador |
| Kandev/interface | Usar como candidato ou referência de Front End; não duplicar o domínio documental do Traycer |
| Claude Code direto | Deja + `CLAUDE.md`/skills |
| Claude Code via Traycer | Mesmo limite do Codex via Traycer |
| Claude Desktop | Pode consumir Deja por MCP; histórico próprio permanece fora |
| Claude Design | Tratar como skill/interface, não memória independente |
| Claude Web/extensão | Sem ingestão local confiável; depender de export/API oficial futura |
| Copilot | Deja cobre CLI; não presumir cobertura integral do IDE/Web |

---

## 6. Governança de memória e revalidação

Histórico recuperado não deve virar instrução automaticamente.

Fluxo recomendado:

```text
1. RECUPERAR
   Deja/Hermes localiza sessões e trechos com origem, data e harness.

2. REVALIDAR
   Operador classifica: vigente, superado, contraditório ou contextual.

3. PROMOVER
   Regra de projeto       → AGENTS.md / CLAUDE.md
   Procedimento repetível → SKILL.md
   Preferência pessoal    → Hermes memory
   Estado temporário      → sessão / todo / handoff

4. REFERENCIAR
   Agentes recebem a instrução canônica; histórico entra como evidência.

5. EXECUTAR
   Promoção ou ratificação nunca autoriza dispatch ou mutação.
```

Princípios governantes:

- identidade antes de significado;
- origem antes de promoção;
- histórico é evidência, não autoridade;
- instrução canônica deve ser versionada;
- memória recuperada deve preservar proveniência, data e estado;
- revalidação deve ser explícita;
- scope, config, binding e dispatch permanecem gates distintos.

---

## 7. Experimentos e validações recomendados

### 7.1 PoC prioritária — Deja-vu

1. Fixar `v0.16.4` ou SHA auditado e verificar checksum, assinatura e SBOM; não instalar por pipe.
2. Usar repositório-laboratório próprio, com config e índice isolados e fontes read-only limitadas.
3. Definir exclusions e trust policy antes da primeira indexação.
4. Manter auto-recall, sync, share, embeddings e instalação global desligados.
5. Rodar `doctor --offline`, indexação controlada e buscas explícitas.
6. Testar português brasileiro, acentos, nomes/caminhos Unicode e sessões compactadas.
7. Conectar primeiro apenas ao Hermes por MCP stdio.
8. Filtrar `remember` para o perfil inicial read-only.
9. Verificar a classificação Hermes por `cwd/git_repo_root` antes de ativar recall contextual.

Critérios de passe:

- uma bateria fixa de oito consultas conhecidas, cobrindo Hermes, Claude Code, Codex e Copilot, possui sessão esperada registrada antes do teste;
- a sessão esperada aparece entre os cinco primeiros resultados em pelo menos sete das oito consultas, com todos os quatro harnesses representados;
- uma consulta negativa não produz afirmação falsa de correspondência;
- fontes excluídas não aparecem;
- nenhum arquivo de origem é alterado;
- redaction segura os casos de controle;
- resultado mostra harness, sessão, data e proveniência;
- conteúdo histórico é enquadrado como não confiável;
- remoção do diretório-laboratório reverte o experimento;
- agrupamento Hermes por projeto é corrigido ou formalmente aceito.

Após o passe, Claude Code, Codex e Copilot entram um por vez. Auto-recall continua desligado até existir policy e budget aprovados.

### 7.2 PoC de interface — projeção do Traycer para o operador

Esta PoC avalia a superfície de interface do Kandev, não uma competição nem migração do Traycer:

1. usar um repositório descartável e bind somente em loopback;
2. projetar um épico e seus tickets existentes no Traycer sem recadastrar o conteúdo;
3. mostrar origem, objetivo, estado, dependências e aprovações do artefato Traycer;
4. separar visualmente `scope`, `config`, `binding` e `dispatch`;
5. permitir seleção e preview sem executar nada;
6. exigir confirmação explícita para um único dispatch autorizado a Hermes, Claude Code ou Codex;
7. devolver runtime, sessão, resultado e evidência à interface;
8. manter a promoção do resultado ao Traycer como ação separada do operador;
9. manter auto-approve desligado, policy MCP explícita e nenhuma exposição direta à rede.

Critérios de passe:

- o artefato Traycer é exibido por identidade estável, sem segunda cópia canônica;
- abrir, selecionar ou pré-visualizar nunca dispara execução;
- o preview identifica objetivo, repositório, runtime e binding antes da confirmação;
- somente o comando explícito de dispatch inicia o runtime;
- resultado e evidência retornam à interface sem alterar automaticamente o Traycer;
- todos os quatro gates permanecem distinguíveis e auditáveis;
- a interface preserva o acesso às interfaces CLI/TUI nativas.

### 7.3 Validação comportamental — i-have-adhd

Reaproveitar somente as regras de restatar estado, mostrar a próxima ação e separar feito de pendente. A validação deve ser opt-in nas skills existentes; não exige instalação de outro runtime.

Critérios de passe:

- três respostas de controle mostram estado atual, próxima ação e separação entre feito e pendente;
- as regras não contradizem Ponytail ou Caveman;
- nenhuma memória, persistência, runtime ou dependência adicional é criada;
- remover a opção restaura o comportamento anterior sem migração.

---

## 8. Gates de decisão

```text
ESTADO ATUAL — DIREÇÃO DOCUMENTADA
- Traycer permanece como plano documental
- Kandev é candidato/referência de interface do operador
- Deja é candidato a plano de evidência histórica
- i-have-adhd é referência comportamental opt-in

RECOMENDADO, MAS AINDA NÃO AUTORIZADO
- PoC isolada do Deja
- PoC de projeção Traycer → interface do operador
- validação textual das regras selecionadas de i-have-adhd

ADOÇÃO — SOMENTE APÓS PASSE E NOVA DECISÃO
- Deja somente após critérios funcionais e de segurança
- interface somente após provar gates sem segunda verdade documental
- regras comportamentais somente após validação sem conflito

NO-GO
- Kandev exposto à rede sem proxy/VPN/auth
- Kandev como substituto ou segunda fonte documental do Traycer
- Auto-recall histórico sem policy de trust
- Promoção automática de memória para instrução
- Dispatch implícito por seleção, preview ou ratificação documental

FORA DESTE ESCOPO
- Temporal
- NPCPy
- JCode
```

---

## 9. Decisão recomendada

Direção ratificada nesta iteração:

- Traycer permanece como fonte documental de épicos, requisitos, tickets e handoffs;
- Kandev é candidato ou referência de Front End operável sobre esse plano;
- Deja permanece candidato a busca e evidência histórica transversal;
- regras selecionadas de `i-have-adhd` permanecem candidatas opt-in.

Ainda não autorizado:

- instalar ou indexar com Deja;
- instalar ou expor Kandev;
- implementar adapter Traycer/interface;
- disparar agentes por essa interface;
- promover automaticamente resultados ao Traycer.

A recomendação principal é preservar o que já funciona: Traycer documenta; Hermes e os harnesses executam; Deja pode recuperar evidência; a interface do operador torna capacidade, preview, gates, dispatch e resultado visíveis. Nenhuma dessas camadas herda automaticamente a autoridade da outra.

---

## 10. Critérios de aceitação deste épico

- [x] problema e contexto explicitados;
- [x] interfaces e agentes afetados identificados;
- [x] seis projetos avaliados e três delimitados no escopo estratégico ativo;
- [x] Temporal, NPCPy e JCode preservados como análise, sem consequência estratégica;
- [x] Traycer reposicionado como plano documental, não concorrente do Kandev;
- [x] Kandev reposicionado como candidato/referência de interface do operador;
- [x] documentação, interface, memória, instruções, busca e execução separados;
- [x] riscos de segurança e maturidade registrados;
- [x] aderência às interfaces locais mapeada;
- [x] arquitetura mínima recomendada;
- [x] provas mínimas e critérios reproduzíveis descritos;
- [x] execução e mutação mantidas fora da ratificação do épico;
- [x] operador ratifica o reposicionamento conceitual Traycer → interface inspirada no Kandev;
- [ ] operador autoriza separadamente qualquer PoC.

---

## 11. Fontes principais

As fontes da avaliação externa ficam limitadas aos três projetos avaliados que permanecem no escopo. O Traycer é o plano documental incumbente do ambiente local, não um dos repositórios candidatos desta pesquisa.

### Deja-vu

- https://github.com/vshulcz/deja-vu
- https://github.com/vshulcz/deja-vu/tree/29910d5783471a528d12342f006bb901bf797c2c
- https://github.com/vshulcz/deja-vu/releases/tag/v0.16.4
- https://raw.githubusercontent.com/vshulcz/deja-vu/v0.16.4/docs/SECURITY-MODEL.md
- https://raw.githubusercontent.com/vshulcz/deja-vu/v0.16.4/internal/sources/hermes.go

### Kandev

- https://github.com/kdlbs/kandev
- https://github.com/kdlbs/kandev/tree/3760f12939f50b0a67b7ca48b2fd9d81e5aa12a8
- https://github.com/kdlbs/kandev/releases/tag/v0.82.0
- https://kandev.ai/docs/agents-and-profiles
- https://github.com/kdlbs/kandev/blob/3760f12939f50b0a67b7ca48b2fd9d81e5aa12a8/docs/public/security.md
- https://github.com/kdlbs/kandev/blob/3760f12939f50b0a67b7ca48b2fd9d81e5aa12a8/docs/public/feature-status.md

### i-have-adhd

- https://github.com/ayghri/i-have-adhd
- https://github.com/ayghri/i-have-adhd/commit/07684c4ab625dd7d1ea6e99e065f60bc0ac6a1ba

### Referências preservadas fora do escopo

- https://github.com/NPC-Worldwide/npcpy
- https://github.com/temporalio/temporal
- https://github.com/1jehuang/jcode

---

## 12. Estado final do registro

Pesquisa documental, inspeção de código remoto e inventário local concluídos. Nenhum dos projetos foi clonado, instalado ou executado. Nenhuma configuração de agente, MCP, serviço, rede ou histórico foi alterada.

**Próximo gate:** autorização explícita e separada do operador para a PoC do Deja, para a PoC de interface Traycer → operador ou para nenhuma delas.
