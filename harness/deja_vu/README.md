# Deja-vu — homologação SSOT-OKF

Capacidade project-owned para homologar busca histórica transversal sem tocar stores reais ou configurações de agentes.

## Executar

```bash
python harness/deja_vu/scripts/homologate.py
```

O comando baixa a release fixada, verifica checksum, attestation e SBOM, cria quatro fontes sintéticas, executa oito consultas e grava o relatório local em `.work/report.json`.

## Testar

```bash
python -m unittest harness/deja_vu/tests/test_homologate.py -v
```

## Limpar

```bash
python harness/deja_vu/scripts/homologate.py --clean
```

## Limites atuais

- não instala globalmente;
- não lê históricos reais;
- não conecta MCP;
- não executa `remember`, sync, share, embeddings, hooks ou auto-recall;
- não promove histórico para instrução canônica.

O próximo gate está no PRD. O resultado sintético não autoriza indexação real.
