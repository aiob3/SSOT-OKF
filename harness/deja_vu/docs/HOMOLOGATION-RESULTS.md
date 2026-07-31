# Evidência de homologação — Deja-vu v0.16.4

- **Execução:** 2026-07-30T20:53:09-03:00
- **Ambiente:** Linux amd64, project-owned, fontes sintéticas
- **Veredito:** PASS

## Release

- Asset: `deja-vu_0.16.4_linux_amd64.tar.gz`
- SHA-256: `66825876fbc4eee2503fb50eb51200b534cc48d1978b5c3621db3133a640b390`
- Checksum publicado: verificado
- GitHub build attestation: verificada
- SBOM SPDX: presente, parseável e com SHA-256 publicado `12d02570caf6a848173fa1b4322f81d1df3a88cac3375df3963f1820cf622565`

## Fontes

| Harness | Sessões | Mensagens | Redactions |
|---|---:|---:|---:|
| Claude Code | 1 | 2 | 1 |
| Codex | 1 | 2 | 0 |
| Copilot | 1 | 2 | 0 |
| Hermes | 1 | 2 | 0 |

## Recuperação

As oito consultas pré-registradas retornaram a sessão esperada no tier `exact`:

- Claude Code: 2/2;
- Codex: 2/2;
- Copilot: 2/2;
- Hermes: 2/2.

Todos os hits aceitos declararam `source.origin=local` e `source.instance=ssot-okf-homologation`.

Consultas com `ação`, `canário`, `âmbar`, `lápis` e `pêssego` preservaram Unicode. A consulta negativa não produziu hit contabilizável.

## Segurança e isolamento

- a credencial sintética foi redigida e não apareceu no índice nem na saída pesquisável;
- os hashes das quatro fontes permaneceram idênticos;
- os hashes das configurações reais existentes permaneceram idênticos;
- o diagnóstico encontrou todas as configurações MCP como `config-missing` no HOME isolado;
- recall e embeddings permaneceram `off`;
- nenhum comando de instalação, escrita de nota, sync, share, hook ou auto-recall foi executado;
- o único acesso de rede foi para baixar e verificar os artefatos públicos da release.

## Reproduzir

```bash
python -m unittest harness/deja_vu/tests/test_homologate.py -v
python harness/deja_vu/scripts/homologate.py
```

O relatório detalhado é regenerado localmente em `.work/report.json` e não é versionado.
Após limpeza total e nova execução, o relatório foi byte-idêntico: SHA-256 `1c3f453e4506c36223ad92220294c1d1f96055a2a80472fc7a52936485f12bad`.

## Próximo gate

Pendente: autorização explícita para apontar uma nova execução a históricos reais em modo read-only. Este PASS não autoriza fontes reais, instalação global, MCP, `remember`, hooks ou auto-recall.
