# H2G2 — guia do Mochileiro para Marte (NASA Space Apps)

Protótipo de apoio a astronauta na cratera Gale (área do Curiosity). Princípio: **pequeno, poderoso e realista**.

## Diretrizes (obrigatórias)

### 1. Dados locais, nunca de fora em tempo de execução
- O sistema roda **offline** (Marte não tem internet; atraso de 4–24 min com a Terra). Toda imagem, tile, panorama, medição e tabela é servida a partir de arquivos locais.
- Download de fontes externas (NASA PDS, MMGIS, Mars Trek, raw images) acontece **só no build/ETL**, nunca na API nem no front.
- Proibido no runtime: URL `http(s)://` externa em `<img>`, `fetch`, CDN de JS/CSS/fontes, tiles remotos. Bibliotecas e fontes ficam vendorizadas no repo (ex.: `web/lib/`).
- Sem dado real → devolver `null` e dizer que não há dado. **Nunca inventar** valor, nome ou posição. Mock só atrás de flag explícita (`source: mock`) e nunca como padrão de entrega.
- Toda linha exibida carrega fonte (instrumento/arquivo PDS) e nível de confiança.
- Teste de aceitação: desligar o Wi-Fi e usar o sistema inteiro.

### 2. Front em HTML + CSS + JS puro
- Sem React, sem bundler, sem `npm install` para o front. Abrir `index.html` servido pela API deve bastar.
- ES modules nativos (`<script type="module">`), `fetch` para a API local, DOM direto.
- Biblioteca só se for pequena e vendorizada (ex.: Pannellum, Leaflet/MapLibre em `lib/`). Justificar cada uma.

### 3. Pequeno
- Backend: Python + FastAPI + SQLite (R-tree nativo). Sem PostGIS, sem serviços extras, sem Docker obrigatório.
- Menos dependências > mais features. Antes de adicionar pacote, ver se a stdlib resolve.
- Uma feature = um módulo pequeno + um endpoint + um componente JS. Sem abstrações especulativas.
- Recortar dados para a janela de interesse (Gale/boxwork) em vez de carregar o planeta.

## Estrutura

| Caminho | O quê |
|---|---|
| `api/` | API FastAPI (F01–F08). Endpoints em `api/main.py`, lógica em módulos planos; F03 em `panorama.py`, F04 em `science_card.py`; `geo.py` é a única geometria |
| `data-pipeline/` | ETL: adapters, `db/schema.sql`, scripts `fetch_*`/`seed_*`; `f03/` = ETL do F03/F04 (config, `data/` de entrada, `panorama_data/`, `collect_panoramas.py`). Saída em `data/local/` (ignorado): banco único `h2g2.sqlite` + `f03/` servido em `/bundle` |
| `web/` | Front HTML/CSS/JS puro (features 01/02/03/04/05/06/08), servido pela API em `/`: visor em tela cheia, minimapa que expande, card de rota |
| `docs/` | Proposta, pitch, plano de produto, `feature-NN-*.md` |
| `subprojetos/f03-f04-victoria/` | Só docs do F03/F04 (código e dados já mesclados em `api/`, `data-pipeline/f03/` e `web/`) |

Features: 01 mapa em camadas · 02 rota+risco · 03 fotos/panorama no ponto · 04 ficha científica · 05 condições REMS/RAD · 06 clima · 07 HUD · 08 agente local · 09 sync Terra–Marte · 10 perigos colaborativos · 11 visor por voz (ids m-A…, comandos em `web/commands.json`). Detalhes em `docs/Plano_Produto_Completo.md`.

## Comandos

Time (raiz): `make build` · `make run` (API :8000) · `make front` · `make test`

Só o ETL do F03/F04 (a partir de `data-pipeline/f03/`): `../../.venv/bin/python etl/build.py` (o `make build` já roda)

## Convenções
- **Tudo em inglês, sem exceção**: (1) todo código e componente novo — nomes de variáveis, funções, classes, arquivos, comentários, chaves JSON, endpoints, colunas SQL; (2) tudo que aparece na interface ou é devolvido pela API — textos da UI, mensagens de erro, rótulos, respostas do agente **e dados exibidos** (CSVs curados, descrições de alvos, notas, tipos); (3) cabeçalhos e conteúdo de CSV/JSON/YAML de entrada. Nada de identificador, dado curado ou texto de interface em português. Dado externo em outro idioma é traduzido no ETL.
- Docs em `docs/` seguem em português. Commits em inglês, imperativo ("Add…", "Fix…").
- Campo novo em `/api/point`: acrescentar, nunca renomear/remover chave existente (contrato compartilhado entre features).
- Doc de feature em `docs/feature-NN-<slug>.md`.
- Geometria marciana: raio 3 396 190 m; uma única implementação de haversine/bearing por app.
