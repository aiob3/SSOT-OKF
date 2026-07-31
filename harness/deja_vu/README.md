# Deja-vu — homologação SSOT-OKF

Capacidade project-owned para homologar busca histórica transversal sem ler stores reais, alterar configurações de agentes ou instalar componentes globalmente.

## Executar

```bash
python -B harness/deja_vu/scripts/homologate.py
```

O comando baixa a release fixada com limite e publicação atômica, verifica checksum e attestation do archive, verifica checksum e estrutura SPDX do SBOM, cria quatro fontes sintéticas, executa oito consultas e grava `.work/report.json`. `docs/HOMOLOGATION-RESULTS.md` é gerado do mesmo report e contém seu SHA-256.

## Testar

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest harness/deja_vu/tests/test_homologate.py -v
ruff check harness/deja_vu/scripts/homologate.py harness/deja_vu/tests/test_homologate.py
```

## Limpar

```bash
python -B harness/deja_vu/scripts/homologate.py --clean
```

`--clean` remove somente `harness/deja_vu/.work`, propaga falhas e confirma a ausência final. A reversibilidade declarada cobre artefatos da homologação; caches criados por outras invocações Python ficam fora desse contrato. Os comandos documentados desabilitam bytecode para não criar `__pycache__`.

## MCP read-only

O wrapper `scripts/mcp_wrapper.py` expõe apenas `recall`, `recall_context` e `blame`, rejeitando `remember` com erro JSON-RPC. Configure o Hermes (ou outro harness) para apontar para ele, não diretamente para `deja mcp`:

```json
{
  "mcpServers": {
    "deja-ssot": {
      "command": "python3",
      "args": ["-B", "/data/SSOT-OKF/harness/deja_vu/scripts/mcp_wrapper.py"]
    }
  }
}
```

O wrapper usa o mesmo ambiente isolado do preview read-only: HOME, XDG, cache, índice e TMPDIR dentro de `.work/real`, com `DEJA_OFFLINE=1`, `DEJA_RECALL=off` e `DEJA_EMBED=off`.

## Limites atuais

- não instala globalmente;
- lê históricos reais somente em modo read-only com índice isolado em `.work/real`;
- não conecta MCP sem o wrapper filtrado;
- não executa `remember`, sync, share, embeddings, hooks ou auto-recall;
- entrega ao Deja somente ambiente allowlisted, `DEJA_OFFLINE=1` e buscas com `--no-embed`;
- não promove histórico para instrução canônica;
- não há sandbox/observador de egress disponível: os controles acima não provam egress zero;
- não é alegada attestation separada do SBOM; a evidência do SBOM é checksum publicado, estrutura SPDX e vínculo com o digest do archive.

O próximo gate está no PRD. O resultado sintético não autoriza indexação real.
