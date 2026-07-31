# PRD — Expansão e continuidade do Deja-vu no harness SSOT-OKF

- **Status:** fases 3 e 4 implementadas, mas com homologação funcional e evidência versionada pendentes; fase 5 permanece pendente
- **Produto:** capacidade de valor agregado do `aiob3/SSOT-OKF`
- **Decisão vigente:** evidência histórica transversal, sem autoridade canônica
- **Próximo gate:** captura do gate funcional das fases 3/4; a decisão da fase 5 continua separada

> Iteração recursiva a partir do épico `ssot-okf-experiment_research.md`. A única evidência versionada atual é sintética; implementação presente não substitui homologação funcional capturada.

## Problem Statement

O operador usa Hermes, Claude Code, Codex e Copilot em superfícies diferentes. Cada harness preserva seu próprio histórico, mas o SSOT-OKF ainda não possui uma consulta transversal homologada que recupere decisões anteriores com origem, data e harness.

Hermes já pesquisa suas próprias sessões. A lacuna é recuperar evidência entre harnesses sem transformar histórico em instrução, sem modificar os stores de origem e sem habilitar execução implícita.

## Solution

Agregar o Deja-vu ao SSOT-OKF como plano local de evidência histórica. A primeira entrega é um harness offline-first que:

1. fixa uma release;
2. verifica checksum e build attestation do archive, além de checksum e estrutura SPDX do SBOM;
3. cria fixtures sintéticas de Hermes, Claude Code, Codex e Copilot;
4. executa o binário publicado como caixa-preta em ambiente project-owned;
5. valida busca, proveniência, Unicode, redaction, integridade e reversibilidade;
6. produz um relatório rastreável de passe ou falha, com timestamp UTC e hashes das autoridades.

A homologação sintética não instala o Deja-vu globalmente, não altera configuração de agentes e não conecta MCP. O código das fases 3/4 prevê stores reais read-only e MCP filtrado, mas isso ainda não é autorização nem evidência de funcionamento real.

## User Stories

1. Como operador, quero validar recuperação transversal antes de indexar históricos reais, para decidir com evidência.
2. Como operador, quero uma release fixada, para repetir o mesmo experimento.
3. Como operador, quero verificar integridade e proveniência do binário, para não executar artefato não auditado.
4. Como operador, quero que o laboratório pertença ao projeto, para evitar estado externo oculto.
5. Como operador, quero começar com fixtures sintéticas, para não expor conversas reais.
6. Como operador, quero cobrir Hermes, Claude Code, Codex e Copilot, para representar o ambiente usado.
7. Como operador, quero resultados esperados definidos antes da execução, para impedir avaliação subjetiva.
8. Como operador, quero origem e sessão em cada resultado, para distinguir evidência de instrução.
9. Como operador, quero validar pt-BR, acentos e Unicode, para detectar corrupção de texto.
10. Como operador, quero validar redaction com credencial sintética, para reduzir propagação de segredos.
11. Como operador, quero uma consulta negativa, para que ausência não vire afirmação.
12. Como operador, quero HOME, cache, config, índice e fontes isolados, para preservar o ambiente pessoal.
13. Como operador, quero `remember`, sync, share, embeddings, hooks e auto-recall desligados, para limitar a fase.
14. Como operador, quero `DEJA_OFFLINE`, `--offline` e `--no-embed`, sem confundir esses controles com prova de egress zero.
15. Como operador, quero um veredito por critério, para decidir o próximo gate.
16. Como operador, quero remover o laboratório com um comando, para garantir reversibilidade.
17. Como operador, quero separar aprovação documental de autorização de fontes reais e MCP.
18. Como agente futuro, quero um comando e uma suíte determinística, para repetir a homologação sem reinterpretar o processo.
19. Como operador, quero consultar históricos reais sem que o Deja escreva neles, para preservar a integridade das fontes.
20. Como operador, quero distinguir mudanças feitas pelo Deja de mudanças feitas por agentes vivos, para não gerar falso positivo de fuga.
21. Como operador, quero que o endpoint MCP exponha apenas tools de leitura, para que o Hermes consulte sem poder escrever notas.
22. Como operador, quero indexação incremental manual, para decidir quando atualizar a visão dos históricos.

## Implementation Decisions

- O projeto vive como capacidade autocontida do harness SSOT-OKF.
- A release homologada é Deja-vu v0.16.4 para Linux amd64.
- O binário, downloads, índice, configuração, fixtures e relatório ficam em diretório project-owned ignorado pelo Git.
- O orquestrador usa somente Python standard library e CLIs já disponíveis.
- SHA-256 do archive e do SBOM é conferido contra `checksums.txt`; a GitHub build attestation é exigida para o archive. Não se alega attestation separada do SBOM quando ela não existe.
- O binário publicado é testado como caixa-preta.
- Hermes usa SQLite sintético; Claude, Codex e Copilot usam JSONL sintético compatível com seus formatos documentados.
- Cada harness possui duas consultas pré-registradas, com termos Unicode e sessão esperada.
- Cada hit aceito deve declarar `source.origin=local` e `source.instance=ssot-okf-homologation`.
- O ambiente do Deja é allowlisted e fixa HOME, XDG cache/config/data/state e TMPDIR dentro de `.work`; remove opt-out de redaction e fixa recall e embeddings como `off`.
- O ambiente do `gh` é separado e recebe somente PATH, diretórios isolados e variáveis de transporte necessárias; tokens e demais segredos não são repassados ao Deja.
- Nenhum comando `install`, `remember`, `sync`, `share`, `embed` ou `update` é executado.
- A implementação das fases 3/4 aponta para `~/.hermes/state.db`, `~/.claude/projects`, `~/.codex` (não `~/.codex/sessions`) e `~/.copilot`; qualquer escrita configurada fica em `.work/real`.
- O novo gate de binding valida tipos/árvores regulares sem symlink ou hardlink e compara conteúdo SHA-256 + estrutura/tipo antes/depois de configuração e quatro fontes, sem `diff_snapshots` ou allowlist volátil; não cobre owner, mode, inode ou outros metadados, nem conclui ausência universal de escritas ou frescor semântico total.
- Antes de cada subprocesso, o gate confere o digest local fixado do binário v0.16.4 derivado do asset já homologado; isso não é uma alegação adicional de attestation.
- Conexão MCP é gate posterior e independente; a tool `remember` permanece fora do perfil de binding inicial. Configuração ou documentação do binding não autorizam a conexão funcional.
- Histórico recuperado é evidência não confiável; instruções canônicas continuam fora do índice.

## Testing Decisions

- A seam principal é o comando completo de homologação e o binário publicado.
- Testes unitários cobrem isolamento do ambiente, symlinks/escape, limpeza fail-closed, downloads/archives limitados, SPDX, attestation, snapshots, MCP e classificação de hits.
- Testes de integração observam apenas comportamento externo do Deja-vu.
- O conjunto possui oito consultas, duas por harness.
- A barra é oito de oito no top 5, todos no tier `exact`, com duas consultas para cada um dos quatro harnesses.
- Todas as consultas acentuadas devem passar.
- A consulta negativa não pode ser contabilizada como evidência.
- A credencial sintética não pode aparecer no índice nem na saída pesquisável.
- Os hashes das fontes devem permanecer idênticos; o snapshot antes/depois deve detectar alteração, remoção ou criação em todos os caminhos de configuração monitorados, inclusive XDG.
- O diagnóstico deve conter Claude Code, Codex, Copilot e Hermes em estado explícito `config-missing` ou `not-installed`; estados ausentes ou desconhecidos falham.
- Sem sandbox/observador de rede, a homologação registra somente `DEJA_OFFLINE`, `--offline` e `--no-embed`; não afirma egress zero.
- O gate pendente das fases 3/4 reutiliza `preview_real.py` para roots e ambiente; o fingerprint vem de `homologate.snapshot_paths`. `deja index` é atualização manual dentro do gate, nunca watcher/cron nem prova de frescor semântico total.

## Acceptance Criteria

Os itens sintéticos abaixo só podem ser marcados por um report da versão endurecida e por `HOMOLOGATION-RESULTS.md` contendo o SHA-256 desse report. Esse relatório não autoriza as fases 3/4: elas exigem evidência funcional versionada do gate específico.

- [x] Release v0.16.4 fixada.
- [x] Checksum do archive verificado.
- [x] Build attestation do archive verificada.
- [x] Checksum e estrutura SPDX do SBOM verificados, sem alegação de attestation separada.
- [x] Quatro harnesses descobertos com caminhos project-owned e contagens exatas.
- [x] Oito de oito consultas recuperaram a sessão esperada no tier `exact`.
- [x] Os hits aceitos carregaram caminho de fixture esperado, origem local e identidade estável da homologação.
- [x] Unicode e pt-BR preservados.
- [x] Redaction aplicada à credencial sintética.
- [x] Consulta negativa não produziu evidência.
- [x] Fontes sintéticas permaneceram byte-idênticas.
- [ ] Snapshot de configuração e fontes reais: implementação de snapshot presente, mas evidência funcional versionada pendente.
- [x] Quatro clientes MCP esperados permaneceram em estado permitido.
- [x] Auto-recall, hooks e escrita de notas permaneceram desabilitados.
- [x] unittest e ruff passaram sem gerar bytecode.
- [x] Report e resultado gerado ficaram ligados por SHA-256.
- [ ] Fase 3 — implementação do preview read-only e roots reais presente; homologação funcional versionada pendente.
- [ ] Fase 3 — gate deve comparar diretamente configuração e quatro fontes antes/depois, sem allowlist volátil, e registrar o resultado capturado.
- [ ] Fase 3 — `DEJA_CODEX_ROOT` está implementado como `~/.codex`; prova funcional contra store real pendente.
- [ ] Fase 4 — wrapper read-only, configuração e onboarding presentes; homologação funcional de sessão MCP pendente.
- [ ] Fase 4 — gate deve provar `recall`, recusa `remember` e estabilidade dos caminhos monitorados em execução capturada.
- [ ] Fase 4 — validador de binding presente; ainda requer report versionado produzido pelo gate funcional.
- [ ] Fase 5 — decisão sobre indexação incremental (manual vs. watcher/cron read-only).
- [ ] Fase 6 — interface do operador sobre Traycer (PRD separado).

## Plano de trabalho

| Fase | Entrega | Estado | Gate seguinte |
|---|---|---|---|
| 0 | Pesquisa e épico reposicionados | concluída | adoção no SSOT-OKF |
| 1 | PRD e seam de teste | concluída | implementação sintética |
| 2 | Homologação sintética Deja-vu | endurecida e reexecutada — PASS | decisão sobre fontes reais |
| 3 | Preview read-only sobre fontes reais | implementação presente; homologação/evidência pendentes | gate funcional capturado |
| 4 | MCP wrapper filtrado + binding Hermes | implementação/configuração presentes; homologação/evidência pendentes | gate funcional capturado |
| 5 | Indexação incremental manual | pendente | decisão sobre watcher/cron |
| 6 | Interface do operador sobre Traycer | PRD futuro | não depende de substituir Traycer |

### Gate atual

`docs/HOMOLOGATION-RESULTS.md` atesta somente a homologação sintética. O código presente das fases 3/4 não autoriza concluir leitura real, binding MCP funcional, nem resultado de `deja index`. O gate funcional futuro deve capturar a sessão e só poderá alegar conteúdo SHA-256 + estrutura/tipo de configuração/fontes monitoradas estáveis e escritas configuradas sob `.work/real`; não cobre owner, mode, inode ou outros metadados. Mesmo o PASS sintético não autoriza:

- instalar o Deja-vu globalmente;
- alterar configuração do Hermes;
- conectar MCP sem o wrapper `scripts/mcp_wrapper.py`;
- habilitar `remember`, hooks ou auto-recall;
- promover evidência para memória curada ou documentação canônica.

## Out of Scope

- Interface Kandev/UI nesta entrega (PRD separado na fase 6).
- Substituição ou alteração do Traycer.
- Temporal, NPCPy ou JCode.
- Instalação global do Deja-vu.
- Wiring MCP sem wrapper filtrado.
- Tool `remember` e curated notes.
- Auto-recall, hooks, plugins e captura pre-compact.
- Embeddings ou serviços de modelo.
- Sync, share, SSH e exportação.
- Deployment, DNS, VPS, Docker ou Traefik.
- Watcher/cron de indexação automática (fase 5 decide).

## Further Notes

- O épico de pesquisa adotado permanece a origem da decisão de produto.
- O repositório está com GitHub Issues desabilitado; este PRD versionado é o registro de planejamento.
- O fluxo de autoridade permanece `scope → config → binding → dispatch`.
- Aprovação documental nunca implica dispatch.
- Traycer continua motor documental e de planejamento; a futura UI do operador é uma capacidade separada.
- A implementação do preview e do binding ainda não prova comportamento em stores reais; o gate pendente não ignora ruído volátil e exige igualdade exata dos fingerprints de conteúdo/estrutura monitorados. Sem defesa atômica contra troca de paths por processo local malicioso entre validação e execução, o gate assume host local cooperativo; não implementa fdexec/sandbox.
- O endpoint MCP filtrado está implementado para `recall`, `recall_context` e `blame`, com `remember` bloqueado; a prova funcional versionada continua pendente.
