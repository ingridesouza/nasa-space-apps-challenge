# H2G2 — guia hiperlocal pra uma Marswalk em Gale

Time **DETON8** · NASA Space Apps Challenge, Salvador 2026.

Mapa hiperlocal da região de boxwork no Monte Sharp (Cratera Gale),
com rota inteligente, alertas de segurança e ficha científica —
pensado como guia de campo pro astronauta durante uma caminhada
(Marswalk), rodando **sem depender de internet** (atraso real de
Marte-Terra: 4-22 min). Por que Gale e não Jezero, critérios de
avaliação e o argumento central do pitch estão em
[`docs/H2G2_Proposta_Projeto_Planejamento.md`](docs/H2G2_Proposta_Projeto_Planejamento.md)
e [`docs/PITCH.md`](docs/PITCH.md).

## Estrutura

| Caminho | O quê |
|---|---|
| `api/` | API FastAPI (feature 01 mapa, 02 rota/A*, 08 alertas+trilha do rover) — também serve `web/` na raiz (`/`), mesma origem. Ver [`api/README.md`](api/README.md) |
| `data-pipeline/` | ETL dos dados reais (Mars Trek, PDS, MMGIS, API de imagens do MSL) — adapters + scripts `fetch_*`/`seed_*`. Ver [`data-pipeline/README.md`](data-pipeline/README.md) |
| `web/` | **Frontend único do projeto**, HTML/CSS/JS puro (features 01/02/08) — sem bundler/`npm install`, MapLibre e fontes vendorizados. `frontend/` React foi removido de verdade em 2026-11-14 (ver nota abaixo). Ver [`docs/migracao-front-html-puro.md`](docs/migracao-front-html-puro.md) |
| `subprojetos/f03-f04-victoria/` | Feature 03 (fotos/panorama no ponto) e 04 (ficha científica) — app própria, HTML/JS puro |
| `docs/` | Proposta de produto, pitch, docs de feature. Ver [`docs/README.md`](docs/README.md) |
| `PROXIMOS-PASSOS.md` | Status técnico real de cada fonte de dado e cada feature -- o doc mais honesto do repo sobre o que funciona de verdade |
| `CLAUDE.md` | Diretrizes de arquitetura pro time -- motivou a migração pro `web/`, ver seção abaixo |
| `data/local/` | Todo o dado real baixado (tiles, DTM/MOLA, fotos, condições) -- gitignored, gerado pelos scripts de `data-pipeline/` |

## Rodar

```bash
cd api && pip install -r requirements.txt && python -m uvicorn main:app --port 8124
```

Abrir `http://127.0.0.1:8124/` — a própria API serve o `web/` (mesma
origem, sem CORS, sem build, sem `npm install`). Com `make`
(Linux/Mac/WSL): `make build && make run` — ver `Makefile` na raiz.

### Subprojeto F03/F04 (Victoria)

Ver instruções próprias em `subprojetos/f03-f04-victoria/`.

## Status por feature

| # | Feature | Status |
|---|---|---|
| 01 | Mapa hiperlocal em camadas (CTX/HiRISE/Relevo/THEMIS, tiles reais) | ✅ |
| 02 | Rota inteligente (A* real: mais segura/mais rápida/mais ciência) + radiação real + indicadores de risco | ✅ — falta paradas intermediárias e "motivo de cada alerta" por trecho |
| 03 | Fotos/panorama no ponto | ✅ no subprojeto `f03-f04-victoria` (a integrar com `api/`) |
| 04 | Ficha científica do ponto | ✅ no subprojeto `f03-f04-victoria` (a integrar com `api/`) |
| 05 | Painel de condições (REMS/RAD) | ✅ |
| 08 | Agente local: alertas por regra + trilha do Curiosity (inclinação medida) | ✅ |
| 06, 07, 09, 10 | Previsão climática, HUD no traje, sync Terra-Marte, perigos colaborativos | não iniciadas |

Detalhe completo, com o que é limitação real de dado (CRISM, AI4Mars)
vs. o que é só trabalho pendente, em [`PROXIMOS-PASSOS.md`](PROXIMOS-PASSOS.md).

## Isso funciona sem internet? ("funcionaria em Marte?")

**Sim, no sentido que importa de verdade: zero chamada de rede em
tempo de execução**, confirmado por auditoria em 2026-11-14 (ver
[`PROXIMOS-PASSOS.md`](PROXIMOS-PASSOS.md)):

- Todo dado real já está cacheado em `data/local/` (~130MB no total —
  tiles, DTM/MOLA, condições REMS/RAD, nomenclatura, waypoints do
  rover, e as ~200 fotos, baixadas de verdade pro disco em vez de
  apontar pra `mars.nasa.gov`).
- Zero chamada de rede em qualquer endpoint da API rodando.
- O frontend (`web/`, HTML/JS puro) vendoriza MapLibre e as fontes
  (`web/lib/`, `web/fonts/`) -- nada de CDN em tempo de execução, nem
  `npm install` (não existe mais `package.json` no projeto).

A única etapa que precisa de internet é a **preparação**
(`pip install`, os scripts de `fetch_*` em `make build`) -- acontece
uma vez, com antecedência, igual instalar qualquer software antes de
uma missão real.

## Migração React → HTML/JS puro: concluída

**2026-11-14**: a migração pedida pelo [`CLAUDE.md`](CLAUDE.md) e
planejada em [`docs/migracao-front-html-puro.md`](docs/migracao-front-html-puro.md)
foi concluída de ponta a ponta -- `web/` é o único frontend do
projeto agora, servido pela própria API (`/`), e `frontend/` (React)
foi removido do repositório de verdade (confirmado: não existe mais
nem em disco nem rastreado pelo git).

Validado ao vivo depois da remoção: `/` serve o `web/`, `/api/route`
devolve as 3 variantes (incluindo "mais ciência" e radiação real,
construídas antes da migração), `/api/point` com alertas, `/tiles` e
`/rover-photos` -- tudo funcionando junto, nada quebrou na troca.

**Bug real encontrado e corrigido nessa migração:** o `Makefile`
atualizado fazia `make test` chamar `test_agente.py` e `test_f03.py`,
que não existem em `api/` (conferido: busca no repo inteiro não acha
nenhum dos dois). `make test` falharia direto. Corrigido pra rodar só
`test_alertas.py`, que existe e passa (6 testes).
