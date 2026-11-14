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
| `web/` | **Frontend atual, HTML/CSS/JS puro** (features 01/02/08) — substitui o `frontend/` React, sem bundler/`npm install`, MapLibre e fontes vendorizados. Ver [`docs/migracao-front-html-puro.md`](docs/migracao-front-html-puro.md) |
| `frontend/` | Mapa React + Vite + MapLibre GL -- **versão anterior, ainda no repo** (ver nota abaixo). Ver [`frontend/README.md`](frontend/README.md) |
| `subprojetos/f03-f04-victoria/` | Feature 03 (fotos/panorama no ponto) e 04 (ficha científica) — app própria, HTML/JS puro |
| `docs/` | Proposta de produto, pitch, docs de feature. Ver [`docs/README.md`](docs/README.md) |
| `PROXIMOS-PASSOS.md` | Status técnico real de cada fonte de dado e cada feature -- o doc mais honesto do repo sobre o que funciona de verdade |
| `CLAUDE.md` | Diretrizes de arquitetura pro time -- ver nota de **divergência em aberto** abaixo |
| `data/local/` | Todo o dado real baixado (tiles, DTM/MOLA, fotos, condições) -- gitignored, gerado pelos scripts de `data-pipeline/` |

## Rodar

### API + frontend atual (`web/`, features 01/02/08)

```bash
cd api && pip install -r requirements.txt && python -m uvicorn main:app --port 8124
```

Abrir `http://127.0.0.1:8124/` — a própria API serve o `web/` (mesma
origem, sem CORS, sem build). Com `make` (Linux/Mac/WSL):
`make build && make run` — ver `Makefile` na raiz.

### Frontend React (versão anterior, ainda funcional)

```bash
cd frontend && npm install && npm run dev
```

Aponta pra mesma API (`VITE_API_BASE_URL`). Mantido rodando em
paralelo até a decisão de remoção (ver nota abaixo) ser executada de
verdade.

### Subprojeto F03/F04 (Victoria)

Ver instruções próprias em `subprojetos/f03-f04-victoria/`.

## Status por feature

| # | Feature | Status |
|---|---|---|
| 01 | Mapa hiperlocal em camadas (CTX/HiRISE/Relevo/THEMIS, tiles reais) | ✅ |
| 02 | Rota inteligente (A* real, mais segura/mais rápida) + indicadores de risco | ✅ MVP — faltam paradas intermediárias e rota "mais ciência" |
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
- O frontend (React/Vite) vira bundle estático no build — não busca
  nada de CDN em tempo de execução.

A única etapa que precisa de internet é a **preparação**
(`npm install`, `pip install`, os scripts de `fetch_*`) — e isso
acontece uma vez, com antecedência, igual instalar qualquer software
antes de uma missão real. Não é diferente entre a versão React e a
versão HTML/JS puro do subprojeto: as duas precisam desse preparo
prévio: o que muda é só a complexidade dessa etapa, não se o sistema
funciona sem internet depois.

**Gap que já foi resolvido no frontend atual:** o `web/` (HTML/JS
puro) auto-hospeda as fontes (`web/fonts/`), copiadas do padrão já
usado em `subprojetos/f03-f04-victoria`. O `frontend/` React antigo
ainda carrega via CDN do Google -- sem internet, cai pra fonte do
sistema (não quebra nada), mas isso só importa enquanto ele continuar
no ar em paralelo.

## Migração React → HTML/JS puro: feita, mas não finalizada

**Atualização (2026-11-14):** a migração pedida pelo [`CLAUDE.md`](CLAUDE.md)
e planejada em [`docs/migracao-front-html-puro.md`](docs/migracao-front-html-puro.md)
já aconteceu -- `web/` existe, é servido pela própria API (`/`), e
reproduz fielmente tudo que estava no React (incluindo o que foi
construído na mesma sessão: rota "mais ciência", dose de radiação
real). Testado ao vivo: API serve `/` com `web/` e `/api/route`
continuam respondendo juntos, sem conflito.

**Mas tem uma imprecisão real que vale registrar**: o doc de migração
diz que a "fase 5 (remover `frontend/`)" foi feita em 2026-11-14 --
**isso não é verdade**. Conferido direto no repo: `frontend/` (React)
ainda existe, intacto, com `node_modules/` e tudo, e continua
funcionando normalmente apontando pra mesma API. A limpeza foi
*documentada* como feita, mas não foi *executada*. Enquanto isso não
for resolvido de propósito (apagar `frontend/`, tirar o CORS, ajustar o
`Makefile` -- os passos que o próprio doc de migração lista na seção
5), os dois frontends continuam coexistindo no repo. Não é um
problema funcional (os dois funcionam, contra a mesma API), só uma
divergência entre o que o doc afirma e o que de fato está no disco.
