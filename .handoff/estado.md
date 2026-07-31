# Handoff — ciclo Deja fail-closed

Atualizado em 2026-07-31T04:40:17-03:00. Este é o state canônico para retomar o trabalho em `/data/SSOT-OKF`.

## Foco da próxima sessão

Preparar e, somente após autorização explícita do operador, executar uma única homologação funcional Hermes/MCP/Deja com configuração, query e oracle controlados. Não integrar ao journal causal e não tratar presença, teste unitário ou execução básica como adoção.

## Norte e decisão vigente

- A evidência versionada atual do Deja é sintética; ela não autoriza leitura real, binding MCP funcional, indexação real nem adoção.
- O changeset fail-closed recebeu GO estático/unitário e revisão contratual sem finding load-bearing.
- Fases 3/4 continuam **NÃO VERIFICADAS funcionalmente** até uma captura real, durável e específica do gate.
- Adoção e integração com o journal causal são decisões posteriores e separadas do operador.

## Referência principal

- Walkthrough: `/home/vcia/.traycer/epics/c9031a27-2991-440c-8011-1184de1cf1f5/artifacts/changeset-walkthroughs/deja-gate-fail-closed/index.md`
- SHA-256 do walkthrough: `96c54db3a3dd488fddaaf6c7c7e47ca54c656f996b775753cae4faec9c463f34`
- O walkthrough contém fluxo, seis arquivos, ordem de revisão, decisões, gotchas, provas e limites; não duplicar seu conteúdo aqui.

## Concluído neste ciclo

- Corrigido o falso PASS em `harness/deja_vu/README.md`, `docs/ONBOARDING.md` e `docs/PRD.md`: implementação presente não substitui homologação real.
- Endurecido `scripts/validate_binding.py`: config exata sem `env`, quatro roots regulares, recusa de symlink/hardlink/especial, digest fixado do binário, indexação manual, revalidações pós-index e no `finally`, sessão MCP correlacionada e claim limitada.
- Criado `tests/test_validate_binding.py` com matriz adversarial isolada.
- Alterado `tests/test_mcp_wrapper.py` para deixar os três roundtrips reais atrás de `DEJA_INTEGRATION=1`.
- Revisão de segurança: GO estático. Revisão contratual final: GO, zero finding load-bearing.
- Nenhum commit foi criado para o changeset; a âncora atual continua sendo o HEAD preexistente `80266a9f4e7783697ffd7772f6074f7a661de14c`.

## Estado Git determinístico

- Branch: `feat/deja-vu-homologation`.
- HEAD local = upstream: `80266a9f4e7783697ffd7772f6074f7a661de14c`.
- Histórico relevante no topo:
  - `80266a9 feat(harness): onboarding doc + binding validator`
  - `de4bf95 docs(prd): mark phase 4 binding attested in Hermes`
  - `8a83de9 feat(harness): filtered MCP wrapper + PRD phase 4 gates`
  - `ded5c0f feat(harness): read-only preview over real operator stores`
  - `d186ee8 fix(harness): harden deja-vu homologation gates`
  - `489db19 feat(harness): homologate deja-vu`
- `git status --short`:
  - ` M harness/deja_vu/README.md`
  - ` M harness/deja_vu/docs/ONBOARDING.md`
  - ` M harness/deja_vu/docs/PRD.md`
  - ` M harness/deja_vu/scripts/validate_binding.py`
  - ` M harness/deja_vu/tests/test_mcp_wrapper.py`
  - `?? harness/deja_vu/tests/test_validate_binding.py`

## Gates reexecutados nesta sessão

- `env -u DEJA_INTEGRATION python3 -B -m unittest discover -s harness/deja_vu/tests -v` → `Ran 62 tests`; `OK (skipped=3)`; exit 0.
- `ruff check harness/deja_vu/scripts harness/deja_vu/tests` → `All checks passed!`; exit 0.
- `git diff --check` → sem saída; exit 0.
- `.work/real` antes/depois → SHA agregado idêntico `3598eb9e2ca07db45a4fae7d81dcef5c7e374c73f6e9f21e727ab064b50884d8`; 211 arquivos; 86.407.210 bytes.
- Os 3 skips são intencionais: `tools/list`, `remember` e `recall` reais exigem `DEJA_INTEGRATION=1`.
- Warning conhecido: `ResourceWarning: unclosed database` em caminho preexistente de SQLite durante `test_command_failures_are_not_accepted`; suite terminou verde. Não mascarar nem atribuir automaticamente ao diff.

## Incidente histórico preservado

Antes de tornar os roundtrips opt-in, um `unittest discover` anterior abriu wrapper/Deja real e atualizou estado derivado em `.work/real`. Não apagar nem reescrever essa evidência. Todas as rodadas posteriores removeram `DEJA_INTEGRATION` e comprovaram `.work/real` estável.

## Pendências operacionais

1. Obter do operador autorização explícita para o gate funcional e fixar:
   - arquivo de configuração-alvo e formato;
   - query controlada;
   - oracle literal de `--expect`.
2. Antes da execução, registrar snapshots de config, quatro fontes e `.work/real`.
3. Executar uma vez `scripts/validate_binding.py`; capturar stdout, stderr, exit code e report sem expor conteúdo sensível.
4. Exigir na evidência: handshake exato, `tools/list` com três tools, `remember=-32601 read-only`, `recall` contendo o oracle, estado do índice e estabilidade pós-execução.
5. Só após PASS real decidir se a evidência será versionada e se PRD/ONBOARDING podem marcar fases 3/4 homologadas.
6. Não decidir fase 5, adoção, watcher/cron ou integração com journal causal por consequência automática desse gate.

## STOPs e regras invioláveis

- **ATESTAR, JAMAIS ESTIMAR:** nenhuma declaração funcional sem comando real, saída e exit code desta sessão.
- Sem autorização explícita: não executar `validate_binding.py` real, `DEJA_INTEGRATION=1`, wrapper/Deja/MCP real ou configuração de harness.
- Não integrar Deja ao journal causal e não promover a branch para `main`.
- Preservar os seis caminhos do diff; não resetar, limpar, reverter ou sobrescrever trabalho preexistente.
- Não fazer commit, push, merge ou alterar configuração real sem pedido textual do operador.
- Não expor segredos, conteúdo de stores, tokens, PII ou configuração sensível no chat/log.
- Um PASS controlado não prova egress zero, ausência universal de writes, frescor total do corpus ou proteção contra TOCTOU em host malicioso.

## Suggested skills

- `check` — reatestar branch, diff e gates seguros antes de pedir autorização para o runtime.
- `traycer-review` — revisar qualquer novo diff decorrente da captura/versionamento.
- `traycer-changeset-walkthrough` — atualizar o guia somente se o changeset realmente mudar.
