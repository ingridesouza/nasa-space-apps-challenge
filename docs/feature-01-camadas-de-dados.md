# Feature 01 · Camadas de dados do mapa: registro de decisões, fontes e cálculos

Registro do trabalho de 14–15/11/2026 sobre as camadas do mapa do recorte do boxwork (Gale, ~3×3 km, lon 137.3586–137.4094 E, lat −4.8263 a −4.7757). Junta, num lugar só:
- o que foi decidido;
- o que foi implementado;
- de onde vem cada dado e para quê;
- como cada número inferido é calculado;
- o que foi testado e descartado.

> Código, endpoints, chaves JSON e IDs de camada em inglês (padronização de 15/11/2026). Docs seguem em português.

---

## 1. Requisito do desafio e cobertura

> "Inclua pelo menos três tipos de dado (óptico, térmico, espectral, topográfico, geofísico, atmosférico, radiação, químico), em camadas ou combinados, dando contexto útil para navegar no local."

| Tipo | No mapa (camada) | Fora do mapa | Medido / inferido |
|---|---|---|---|
| Óptico | CTX, HiRISE | panoramas e fotos (F03) | medido |
| Topográfico | Relevo, Risco de inclinação, Sol direto e sombra | rota A* (F02) | medido (DTM); risco = estimado; sol = inferido |
| Térmico | Inércia térmica (THEMIS) | — | medido |
| Atmosférico | REMS na trilha | painel de condições (F05), previsão (F06) | medido |
| Radiação | — | painel de condições (F05) | medido |
| Químico / espectral | — | ficha científica (F04): APXS, ChemCam, CheMin, CRISM | medido |

**Quatro tipos estão no mapa como camada**: óptico, topográfico, térmico e atmosférico. Seis estão no sistema. A combinação entre camadas já existe em três lugares:
- a rota usa a inclinação do DTM;
- `/api/point` junta elevação, inclinação, risco e inércia térmica no mesmo ponto;
- a camada de sol usa o tempo da rota para calcular a hora de chegada.

---

## 2. Camadas: o que é, de onde vem, como é calculada

### 2.1 CTX e HiRISE (óptico)

| | CTX | HiRISE |
|---|---|---|
| Produto | `Gale_CTX_BlockAdj_dd` | `curiosity_hirise_mosaic` |
| Fonte | Mars Trek WMTS | Mars Trek WMTS |
| Resolução local | ~10 m (z12) | ~0,6 m (z16) |
| Uso | base de contexto | base de detalhe |

Os mosaicos são só em preto e branco em Gale.

### 2.2 Relevo (topográfico)

- **Dado:** DTM HiRISE `Gale_DEM_SMG_1m` (Mars Trek ImageServer), recorte de 512×512, ~5,9 m/px.
- **Cálculo:** hillshade de Horn com luz fixa do noroeste (315°, 45°). É convenção cartográfica, não o Sol real.
- **Decisão (15/11):** a camada virou **sobreposição transparente** (`build_hillshade_rgba` em `api/mosaics.py`):
  - terreno plano fica transparente;
  - o que fica mais claro que o plano vira branco, o mais escuro vira preto;
  - a opacidade cresce com a diferença, com contraste esticado pelo percentil 98 do recorte.
- **Por quê:** a versão antiga era cinza opaco a 70% e lavava a HiRISE como um véu.

### 2.3 Risco de inclinação (topográfico, estimado)

- **Dado:** DTM de 5,9 m × `tilt` (atitude) do Curiosity em 293 paradas (MSL_waypoints, MMGIS).
- **Cálculo** (`api/forecast.py`):
  - para cada faixa de inclinação do mapa (0–7, 7–10, 10–15, ≥15°), conta-se a fração de paradas em que o rover mediu ≥15°;
  - cada pixel é pintado por essa frequência: âmbar de 20% a 50%, vermelho a partir de 50% (só se a faixa tiver ≥20 paradas).
- **Natureza:** **frequência histórica de subestimação do DTM, não previsão.** Viés de seleção (o rover só para em terreno seguro), amostra pequena acima de 15° (5 paradas) e nenhuma validação cruzada. Detalhes em `docs/feature-06-previsao-clima.md`.
- **Correção (14/11):** o registro `predicted_risk` faltava no banco e a camada nunca aparecia. Foi resolvido rodando `populate_raster_registry.py`.

### 2.4 Inércia térmica (térmico, medido)

- **Dado:** mosaico global quantitativo de inércia térmica do THEMIS (USGS Astropedia), tile `THEMIS_TI_Mosaic_Quant_30S120E_100mpp.cub`, multi-ano.
- **ETL** (`data-pipeline/scripts/fetch_themis_ti.py`):
  - o rasterio lê por `/vsicurl/` só a janela do recorte (o arquivo inteiro tem 2,5 GB);
  - o transform é convertido de eqc para graus, sem reamostrar;
  - resultado: GeoTIFF de 42×42 células, TI de 260 a 503 (mediana 390).
- **Exibição** (`api/thermal.py`): escala fixa de 200 a 550, células reais de 100 m (`nearest`), legenda "solto ↔ firme". `/api/point` ganhou `thermal_inertia`.
- **Leitura física:** TI alta = rocha ou solo cimentado (varia pouco ao longo do dia). TI baixa = areia ou poeira (esquenta e esfria rápido). Cortes numéricos de classe não foram aplicados porque exigem citação (Fergason et al. 2006).
- **Decisão (14/11):** substitui a THEMIS Day IR (WMTS, só imagem). A Day IR ficava borrada em 3 km e não tinha valor numérico.

### 2.5 Atmosfera: REMS na trilha (atmosférico, medido)

- **Dado:** REMS RNV (PDS Atmospheres), 180 leituras por sol, em cada sol com parada do rover no recorte. São 241 sóis (3951–4843). A posição usada é a da **última parada do sol** (MSL_waypoints).
- **ETL:** `data-pipeline/scripts/cache_atmosphere_track.py`, retomável, ~13 s por sol. Reaproveita o resumo da climatologia da F06 e grava `data/local/conditions/atmosphere_track.json`. Guarda também a dose RAD de cada sol (para uso futuro).
- **API:** `api/atmosphere.py`, `/api/atmosphere/track` (GeoJSON).
  - Sóis de 4844 a 5073 vêm com `null` e o motivo ("sol ainda não publicado no PDS").
  - Sóis sem produto no PDS vêm com "sem produto REMS no PDS".
- **Variáveis no seletor:** temperatura máxima do ar, temperatura mínima do ar e pressão média.
- **Natureza:** o REMS mede só onde o rover está. **A cor ao longo da trilha mostra sobretudo a estação, não o lugar.** A temperatura máxima vem das 180 leituras amostradas, não do pico real (subestima um pouco).
- **Decisão:** não interpolar entre pontos, porque seria inventar valor.

### 2.6 Sol direto e sombra (iluminação, inferido)

- **Dados:**
  - posição do Sol pelo Mars24 (`api/mars_time.py`);
  - DTM HiRISE **em 1 m nativo** (3011×2999), reduzido a 2 m;
  - MOLA regional ±1° (463 m/px) para o horizonte distante (o Monte Sharp fora do recorte).
  - Os dois relevos são baixados por `data-pipeline/scripts/fetch_insolation_relief.py`.
- **Cálculo** (`api/insolation.py`), para um sol e uma hora solar verdadeira (LTST):
  1. Elevação e azimute do Sol a partir da declinação (vinda do Ls) e do ângulo horário.
  2. Incidência = cosseno entre a normal do terreno (gradiente do DTM) e o vetor do Sol.
  3. **Sombra de perto:** caminhada sobre o DTM na direção do Sol, com passo crescente (2% da distância). Um pixel fica na sombra se algum ponto à frente estiver acima da linha de visada.
  4. **Sombra de longe:** perfil do MOLA de 2 a 60 km na direção do Sol, calculado numa grade 8× mais grossa.
  5. **Destino:** categoria pela área de ~20 m em volta: ao sol (<20% de sombra), sombra parcial (20–80%) ou na sombra (≥80%).
  6. A irradiância é `1361/r² × cos(i)`: topo da atmosfera, sem poeira, limite superior. Fica **só no endpoint**, não na interface.
- **Relógio:** `/api/clock`, simulado. Configura com `H2G2_CLOCK="SOL@HH:MM"` e anda em tempo real. A hora local sai do Mars24 (LMST + equação do tempo).
  - **Chegada** = agora + tempo de ida da rota (`estimated_time_min`), convertido para hora marciana.
- **Interface:** atalhos "agora" e "chegada", slider de 05h a 19h, "Destino: ao sol / sombra parcial / na sombra".
- **Validação:** ver §4.2 e `docs/feature-01-camada-insolacao.md`.
- **Decisão:** o DTM de 1 m é usado **só aqui**. Rota, inclinação e risco ficaram no de 5,9 m, em que foram calibrados; trocar mudaria a calibração e deixaria o A* bem mais lento.

---

## 3. Fontes por finalidade

| Fonte | Produto / acesso | Para quê | Quando baixa |
|---|---|---|---|
| Mars Trek WMTS | CTX `Gale_CTX_BlockAdj_dd`, HiRISE `curiosity_hirise_mosaic` | camadas ópticas | build |
| Mars Trek ImageServer | DTM `Gale_DEM_SMG_1m`, recorte de 512 px (~5,9 m) | relevo, inclinação, risco, rota | build |
| Mars Trek ImageServer | DTM `Gale_DEM_SMG_1m`, 1 m nativo | insolação e sombra de perto | build |
| Mars Trek ImageServer | MOLA `mola128_mola64_merge…`, ±1°, 463 m | horizonte distante; elevação secundária | build |
| USGS Astropedia | THEMIS TI quantitativo 100 m (`/vsicurl/`) | inércia térmica | build |
| PDS Atmospheres | MSL REMS RNV | atmosfera na trilha, condições, climatologia | build |
| PDS-PPI | MSL RAD RDR (detector E) | dose diária (condições; cache da trilha) | build |
| MMGIS | `MSL_waypoints.json` | posição por sol, `tilt` do rover, trilha | build |
| Mars24 (algoritmo, NASA GISS) | fórmulas (sem download) | Ls, sol, hora local, posição do Sol | runtime local |
| PDS HiRISE RDR | PSP_009294_1750 (JP2, só o recorte, por `/vsicurl/`) | **só validação**; nada fica no repo | teste |

Tudo é servido offline em runtime. Downloads só no `make build`.

---

## 4. Validações feitas

### 4.1 Posição do Sol × metadados HiRISE

Em 4 observações (PSP_009294, ESP_026924, ESP_040770, ESP_049552), a elevação do Sol pelo modelo difere ≤ 0,1° da que os metadados das fotos dão.

### 4.2 Sombreamento × foto HiRISE PSP_009294_1750

Condições da foto: Ls 101°, hora solar 15h26, Sol a 32° de altura, emissão de 2,3°.

| | Sol real | Sol oposto | Girado 90° | 09h30 |
|---|---|---|---|---|
| Correlação brilho × incidência (10 m) | **+0,38** | −0,35 | −0,19 | −0,24 |
| Sombras previstas escuras na foto (tolerância de 4 m) | 25% | 8% | — | — |

- **Validado:** posição do Sol; lado iluminado × escuro do relevo a ~10 m.
- **Não validado:** sombra num ponto exato (o escuro fino vem de cristas < 2 m); Sol baixo (não há HiRISE do recorte fora de 14–16h).

### 4.3 Dados

- **Inércia térmica:** a leitura da janela confirmou valores reais e sem nodata.
- **REMS na trilha:** 241 de 241 sóis com dado; RAD em 239 (faltam 4442 e 4483 no PDS).
- **Dose RAD de 1883 µGy/dia (sol 4190) e 454 (sol 4191):** é a tempestade solar de 20–21/05/2024, evento real, não erro.

---

## 5. Testado e descartado

| Ideia | Resultado | Decisão |
|---|---|---|
| THEMIS Day IR como camada térmica | só imagem, ~100 m, borrada em 3 km | trocada pela TI quantitativa |
| Temperatura do ar e pressão fora da trilha | pressão varia 1–2% em 3 km; o ar não tem base para variar | não feito |
| Mapa de temperatura do chão fora da trilha (REMS + insolação + TI) | a estação domina (RMSE 6,9 °C); relevo e TI não acrescentam (correlação −0,03 / +0,02) | não feito; **o teste usou o canal errado, ver §6** |
| Temperatura do chão como opção da atmosfera | canal B do GTS dá 35–39 °C ao meio-dia (implausível); o canal A dá 0–7 °C | **removida** do seletor |
| "Mapa de radiação" por lugar | a dose varia com o dia (ciclo solar, tempestades), não com a posição em 3 km | não feito |
| TES Dust Cover Index e TES Thermal Inertia (Mars Trek) | ~1 pixel no recorte; o Trek só dá imagem sem legenda; TES TI (97–274) diverge da THEMIS (260–503), sem explicação verificada | não usados |
| CRISM como camada do Mars Trek | as camadas do Trek não cobrem Gale | não usado (os cubos MTRDR do recorte estão na F04) |

---

## 6. Pendências conhecidas

1. **GTS (temperatura do chão):** migrar do canal B para o A em `pds_rems.py`, `cache_climatology.py` e na trilha. Depois, refazer a climatologia e o teste do chão. Afeta a previsão do chão da F06.
2. **Risco de inclinação:** renomear de "previsto" para "frequência histórica"; mostrar `n` e intervalo de confiança; validação cruzada espacial. Conferir também se `_slope_degrees` e `_slope_grid_deg` dão o mesmo valor.
3. **Dose RAD no mapa:** opção "dose do dia" no seletor da trilha, marcando a tempestade de 05/2024 e com rótulo "varia com o dia, não com o lugar".
4. **Inércia térmica na rota:** penalizar TI baixa no custo do A*.
5. **Hora de chegada:** o modelo de velocidade da rota nunca foi validado. Mostrar uma faixa em vez de um horário único.
6. **Ano das fontes:** CTX, HiRISE e o mosaico do DTM não têm data de aquisição registrada.
