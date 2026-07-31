<!-- generated-by: harness/deja_vu/scripts/homologate.py; source: .work/report.json -->
# Evidência de homologação — Deja-vu v0.16.4

- **Execução UTC:** 2026-07-31T00:32:40.229406Z
- **Ambiente:** synthetic-project-owned
- **Veredito:** PASS
- **Relatório local:** `.work/report.json` (SHA-256 `e9dec410befb05731d36c8b18e8182a01cc73cf5fa6aa3eeca428f831110429c`)

## Release

- Archive: `deja-vu_0.16.4_linux_amd64.tar.gz`; SHA-256 `66825876fbc4eee2503fb50eb51200b534cc48d1978b5c3621db3133a640b390`; checksum verificado.
- Attestation do archive: `verified`; repositório `vshulcz/deja-vu`.
- Identidade sanitizada: `https://github.com/vshulcz/deja-vu/.github/workflows/release.yml@refs/tags/v0.16.4`; source digest `f5f8da0a98100f043857243098aaa0ac82df41c2`.
- SBOM: `deja-vu_0.16.4_linux_amd64.tar.gz.spdx.json`; SHA-256 `12d02570caf6a848173fa1b4322f81d1df3a88cac3375df3963f1820cf622565`; `SPDX-2.3` validado e ligado ao digest do archive.
- Não foi publicada/exigida attestation separada para o SBOM; sua evidência é checksum + estrutura SPDX.

## Qualidade e recuperação

- unittest: PASS.
- ruff: PASS.
- claude: 2/2 no tier `exact`.
- codex: 2/2 no tier `exact`.
- copilot: 2/2 no tier `exact`.
- hermes: 2/2 no tier `exact`.

## Critérios

| Critério | Resultado |
|---|---|
| `version_pinned` | PASS |
| `synthetic_sources_exact` | PASS |
| `retrieval_8_of_8_exact` | PASS |
| `unicode` | PASS |
| `negative_is_not_claimed` | PASS |
| `redaction` | PASS |
| `sources_unchanged` | PASS |
| `live_configs_unchanged` | PASS |
| `mcp_unwired` | PASS |
| `project_unittest` | PASS |
| `ruff` | PASS |

## Limite de rede

O Deja recebeu `DEJA_OFFLINE=1`; `doctor` recebeu `--offline`; buscas receberam `--no-embed`.
Não houve sandbox/observador de egress disponível, portanto este relatório não afirma egress zero.

## Gate

Este resultado cobre somente fixtures sintéticas project-owned. Não autoriza fontes reais, instalação global, MCP, `remember`, hooks ou auto-recall.
