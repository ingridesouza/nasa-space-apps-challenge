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
| `web/` | **Frontend único do projeto**, HTML/CSS/JS puro (features 01 a 08) — sem bundler/`npm install`, MapLibre e fontes vendorizados. `frontend/` React foi removido de verdade em 2026-11-14 (ver nota abaixo). Ver [`docs/migracao-front-html-puro.md`](docs/migracao-front-html-puro.md) |
| `subprojetos/f03-f04-victoria/` | Docs da feature 03 (fotos/panorama no ponto) e 04 (ficha científica). Código em `api/panorama.py` e `api/ficha.py`, ETL em `data-pipeline/f03/` |
| `docs/` | Proposta de produto, pitch, docs de feature. Ver [`docs/README.md`](docs/README.md) |
| `PROXIMOS-PASSOS.md` | Status técnico real de cada fonte de dado e cada feature -- o doc mais honesto do repo sobre o que funciona de verdade |
| `CLAUDE.md` | Diretrizes de arquitetura pro time -- motivou a migração pro `web/`, ver seção abaixo |
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

### F03/F04 (panorama e ficha científica)

O `make build` já roda o ETL (`data-pipeline/f03/etl/build.py`). Ele grava as tabelas
`photos`, `panoramas`, `targets`, `measurements` no `data/local/h2g2.sqlite` e os arquivos em
`data/local/f03/` (servidos em `/bundle`). O front antigo do F03/F04 fica em
http://localhost:8000/f03/ até os fronts serem juntados.

## Status por feature

| # | Feature | Status |
|---|---|---|
| 01 | Mapa hiperlocal em camadas (CTX/HiRISE/Relevo/THEMIS, tiles reais) | ✅ |
| 02 | Rota inteligente (A* real: mais segura/mais rápida/mais ciência) + radiação real + indicadores de risco | ✅ — falta paradas intermediárias e "motivo de cada alerta" por trecho |
| 03 | Fotos/panorama no ponto | ✅ panorama e fotos na tela principal (fotos ainda da lista antiga, ver raio-x) |
| 04 | Ficha científica do ponto | ✅ medições reais do PDS (APXS, CheMin, ChemCam) |
| 05 | Painel de condições (REMS/RAD) | ✅ + hora/estação marciana e alerta de dado antigo |
| 06 | Previsão climática local | ✅ estação + anomalia, previsto × medido, janela de EVA na rota |
| 07 | Modo traje (HUD) | 🟡 versão mínima: falta minimapa e trilha de volta |
| 08 | Agente local: alertas por regra + perguntas (Gemma local) + voz de saída | 🟡 falta microfone e rota no contexto |
| 09 | Sync Terra-Marte | não iniciada (pitch) |

O que falta, por gravidade: [`docs/raio-x-implementacao.md`](docs/raio-x-implementacao.md).

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
