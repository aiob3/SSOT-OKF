# PRD — Homologação do Deja-vu no harness SSOT-OKF

- **Status:** fase sintética implementada e homologada
- **Produto:** capacidade de valor agregado do `aiob3/SSOT-OKF`
- **Decisão vigente:** evidência histórica transversal, sem autoridade canônica
- **Próximo gate:** autorização separada para fontes reais em modo read-only

## Problem Statement

O operador usa Hermes, Claude Code, Codex e Copilot em superfícies diferentes. Cada harness preserva seu próprio histórico, mas o SSOT-OKF ainda não possui uma consulta transversal homologada que recupere decisões anteriores com origem, data e harness.

Hermes já pesquisa suas próprias sessões. A lacuna é recuperar evidência entre harnesses sem transformar histórico em instrução, sem modificar os stores de origem e sem habilitar execução implícita.

## Solution

Agregar o Deja-vu ao SSOT-OKF como plano local de evidência histórica. A primeira entrega é um harness offline-first que:

1. fixa uma release;
2. verifica checksum, build attestation e SBOM;
3. cria fixtures sintéticas de Hermes, Claude Code, Codex e Copilot;
4. executa o binário publicado como caixa-preta em ambiente project-owned;
5. valida busca, proveniência, Unicode, redaction, integridade e reversibilidade;
6. produz um relatório determinístico de passe ou falha.

A homologação sintética não instala o Deja-vu globalmente, não lê históricos reais, não altera configuração de agentes e não conecta MCP.

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
14. Como operador, quero diagnóstico offline, para excluir tráfego funcional implícito.
15. Como operador, quero um veredito por critério, para decidir o próximo gate.
16. Como operador, quero remover o laboratório com um comando, para garantir reversibilidade.
17. Como operador, quero separar aprovação documental de autorização de fontes reais e MCP.
18. Como agente futuro, quero um comando e uma suíte determinística, para repetir a homologação sem reinterpretar o processo.

## Implementation Decisions

- O projeto vive como capacidade autocontida do harness SSOT-OKF.
- A release homologada é Deja-vu v0.16.4 para Linux amd64.
- O binário, downloads, índice, configuração, fixtures e relatório ficam em diretório project-owned ignorado pelo Git.
- O orquestrador usa somente Python standard library e CLIs já disponíveis.
- SHA-256 é conferido contra `checksums.txt`; GitHub build attestation e SBOM também são exigidos.
- O binário publicado é testado como caixa-preta.
- Hermes usa SQLite sintético; Claude, Codex e Copilot usam JSONL sintético compatível com seus formatos documentados.
- Cada harness possui duas consultas pré-registradas, com termos Unicode e sessão esperada.
- Cada hit aceito deve declarar `source.origin=local` e `source.instance=ssot-okf-homologation`.
- O ambiente remove qualquer opt-out de redaction e fixa recall e embeddings como `off`.
- Nenhum comando `install`, `remember`, `sync`, `share`, `embed` ou `update` é executado.
- Indexação real e conexão MCP são gates posteriores e independentes.
- Histórico recuperado é evidência não confiável; instruções canônicas continuam fora do índice.

## Testing Decisions

- A seam principal é o comando completo de homologação e o binário publicado.
- Testes unitários cobrem isolamento do ambiente, geração de fixtures, checksum e classificação de hits.
- Testes de integração observam apenas comportamento externo do Deja-vu.
- O conjunto possui oito consultas, duas por harness.
- A barra mínima é sete de oito no top 5, com os quatro harnesses representados.
- Todas as consultas acentuadas devem passar.
- A consulta negativa não pode ser contabilizada como evidência.
- A credencial sintética não pode aparecer no índice nem na saída pesquisável.
- Os hashes das fontes e das configurações reais existentes devem permanecer idênticos.
- O diagnóstico deve confirmar ausência de MCP conectado no ambiente isolado.

## Acceptance Criteria

- [x] Release v0.16.4 fixada.
- [x] Checksum verificado.
- [x] Build attestation verificada.
- [x] SBOM presente e parseável.
- [x] Quatro harnesses descobertos.
- [x] Oito de oito consultas recuperaram a sessão esperada no tier `exact`.
- [x] Os hits aceitos carregaram origem local e identidade estável da homologação.
- [x] Unicode e pt-BR preservados.
- [x] Redaction aplicada à credencial sintética.
- [x] Consulta negativa não produziu evidência.
- [x] Fontes sintéticas permaneceram byte-idênticas.
- [x] Configurações reais existentes permaneceram byte-idênticas.
- [x] MCP permaneceu desconectado.
- [x] Auto-recall, hooks e escrita de notas permaneceram desabilitados.
- [x] Relatório reproduzível gerado.

## Plano de trabalho

| Fase | Entrega | Estado | Gate seguinte |
|---|---|---|---|
| 0 | Pesquisa e épico reposicionados | concluída | adoção no SSOT-OKF |
| 1 | PRD e seam de teste | concluída | implementação sintética |
| 2 | Homologação sintética Deja-vu | concluída — PASS | decisão sobre fontes reais |
| 3 | Indexação de fontes reais | pendente | autorização explícita de scope + config |
| 4 | MCP manual read-only | pendente | binding e policy que excluam `remember` |
| 5 | Operação assistida | pendente | decisão separada sobre recall por demanda |
| 6 | Interface do operador sobre Traycer | PRD futuro | não depende de substituir Traycer |

### Gate atual

A execução concluída autoriza somente a conclusão de que a fase sintética passou. Ela não autoriza:

- ler históricos reais;
- instalar o Deja-vu globalmente;
- alterar configuração do Hermes;
- conectar MCP;
- habilitar `remember`, hooks ou auto-recall;
- promover evidência para memória curada ou documentação canônica.

## Out of Scope

- Interface Kandev/UI nesta entrega.
- Substituição ou alteração do Traycer.
- Temporal, NPCPy ou JCode.
- Instalação global do Deja-vu.
- Históricos reais na fase sintética.
- Wiring MCP.
- Tool `remember` e curated notes.
- Auto-recall, hooks, plugins e captura pre-compact.
- Embeddings ou serviços de modelo.
- Sync, share, SSH e exportação.
- Deployment, DNS, VPS, Docker ou Traefik.

## Further Notes

- O épico de pesquisa adotado permanece a origem da decisão de produto.
- O repositório está com GitHub Issues desabilitado; este PRD versionado é o registro de planejamento.
- O fluxo de autoridade permanece `scope → config → binding → dispatch`.
- Aprovação documental nunca implica dispatch.
- Traycer continua motor documental e de planejamento; a futura UI do operador é uma capacidade separada.
