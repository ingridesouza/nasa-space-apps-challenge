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
| `frontend/` | Mapa React + Vite + MapLibre GL (features 01/02/08 no navegador). Ver [`frontend/README.md`](frontend/README.md) |
| `subprojetos/f03-f04-victoria/` | Feature 03 (fotos/panorama no ponto) e 04 (ficha científica) — app própria, HTML/JS puro |
| `docs/` | Proposta de produto, pitch, docs de feature. Ver [`docs/README.md`](docs/README.md) |
| `PROXIMOS-PASSOS.md` | Status técnico real de cada fonte de dado e cada feature -- o doc mais honesto do repo sobre o que funciona de verdade |
| `CLAUDE.md` | Diretrizes de arquitetura pro time -- ver nota de **divergência em aberto** abaixo |
| `data/local/` | Todo o dado real baixado (tiles, DTM/MOLA, fotos, condições) -- gitignored, gerado pelos scripts de `data-pipeline/` |

## Rodar

### API + frontend React (features 01/02/08)

```bash
cd api && pip install -r requirements.txt && python -m uvicorn main:app --port 8124
cd frontend && npm install && npm run dev
```

No Windows, sem `make` disponível, use os dois comandos acima direto
(é como este projeto foi rodado e testado durante o desenvolvimento).
Com `make` (Linux/Mac/WSL): `make build && make run` (API) `+ make front`
— ver `Makefile` na raiz.

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

**Gap real, não crítico:** as fontes do app React (`Chakra Petch` etc.)
carregam via CDN do Google — sem internet, cai pra fonte do sistema,
não quebra nada. Dá pra auto-hospedar (o subprojeto `f03-f04-victoria`
já faz isso, dá pra copiar o padrão).

## Divergência em aberto: React vs. HTML/JS puro

O [`CLAUDE.md`](CLAUDE.md) (diretriz de arquitetura mais recente do
time) declara o `frontend/` (React/Vite) como **"legado a migrar"** e
pede HTML/CSS/JS puro sem framework daqui pra frente, no padrão do
subprojeto `f03-f04-victoria`. Isso ainda não reflete o estado real do
projeto: o `frontend/` React é o que está construído, testado e
funcionando (mapa com tiles reais, rota A*, alertas, trilha do rover)
— não é legado no sentido de "abandonado", é o core ativo da feature
01/02 até agora.

A motivação do `CLAUDE.md` parece ser reduzir a complexidade da etapa
de **preparo** (zero bundler, zero `npm install`, só abrir um
`index.html`), não uma falha de funcionamento offline do React (que já
está confirmado funcionando, ver seção acima). **Essa divergência
ainda não foi resolvida pelo time** -- decidir se/quando migrar o
`frontend/` pro padrão HTML/JS puro é uma decisão de produto em
aberto, não algo que este README resolve sozinho.
