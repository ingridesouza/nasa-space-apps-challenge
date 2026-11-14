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
| `api/` | API FastAPI (feature 01 mapa, 02 rota/A*, 08 alertas+trilha do rover). Ver [`api/README.md`](api/README.md) |
| `data-pipeline/` | ETL dos dados reais (Mars Trek, PDS, MMGIS, API de imagens do MSL) — adapters + scripts `fetch_*`/`seed_*`. Ver [`data-pipeline/README.md`](data-pipeline/README.md) |
| `web/` | Mapa em HTML/CSS/JS puro + MapLibre GL vendorizado (features 01/02/08), servido pela própria API em `/` |
| `subprojetos/f03-f04-victoria/` | Feature 03 (fotos/panorama no ponto) e 04 (ficha científica) — app própria, HTML/JS puro |
| `docs/` | Proposta de produto, pitch, docs de feature. Ver [`docs/README.md`](docs/README.md) |
| `PROXIMOS-PASSOS.md` | Status técnico real de cada fonte de dado e cada feature -- o doc mais honesto do repo sobre o que funciona de verdade |
| `CLAUDE.md` | Diretrizes de arquitetura pro time |
| `data/local/` | Todo o dado real baixado (tiles, DTM/MOLA, fotos, condições) -- gitignored, gerado pelos scripts de `data-pipeline/` |

## Rodar

### API + mapa (features 01/02/08)

```bash
make build   # uma vez, com internet: dependências + dados reais em data/local/
make run     # API e mapa em http://localhost:8000
```

Agente local (`/api/ask`): instale o [Ollama](https://ollama.com) uma vez. O `make build`
baixa o modelo `gemma3:4b` (3,3 GB) para `data/local/ollama/`, e o `make run` sobe o
Ollama lendo dessa pasta. O modelo fica fora do git (passa do limite do GitHub). Levar o pacote para outra máquina
ainda não funciona só copiando `data/local/` (ver item 5 de `docs/raio-x-implementacao.md`).

Sem `make` (Windows): `cd api && pip install -r requirements.txt && python -m uvicorn main:app --port 8000`
e abrir http://localhost:8000. Não há `npm install` nem build de front.

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
- O mapa (`web/`) usa só arquivos do repo: MapLibre e fontes
  vendorizados em `web/lib/` e `web/fonts/`, sem CDN.

A única etapa que precisa de internet é a **preparação**
(`pip install` e os scripts de `fetch_*`), feita uma vez, com
antecedência, igual instalar qualquer software antes de uma missão real.
