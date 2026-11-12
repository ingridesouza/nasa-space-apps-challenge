# Feature 03 · Panorama no ponto — Plano de construção (H2G2)

Nov 10, 2026 · @vic

## O entregável decidido

O astronauta seleciona um ponto do boxwork, informando latitude e longitude em duas caixas que simulam o clique no mapa, e o H2G2 abre o panorama 360° real tirado pelo Curiosity mais perto dali, já virado para o ponto clicado. Embaixo do panorama aparecem as fotos estáticas próximas e o recorte orbital HiRISE do lugar.

**Fluxo de uso:**

1. Latitude e longitude digitadas em duas caixas, que simulam o clique no mapa (área de \~3 × 3 km do boxwork, Monte Sharp, Cratera Gale). São os únicos dados de entrada.
2. Busca do panorama mais próximo num raio de 300 m.
3. O visualizador 360 abre com a câmera apontada na direção do ponto informado, vista a partir da parada do rover.
4. Abaixo: faixa de até 20 fotos próximas (raio de 200 m), ordenadas por distância, e o recorte HiRISE de 100 × 100 m.
5. Sem panorama no raio: só as fotos e a mensagem “nenhum panorama a menos de 300 m”.

**Regras de honestidade da interface:**

- A distância é de onde a imagem foi tirada, nunca do que ela mostra: “panorama tirado a \~90 m daqui”.
- Distâncias arredondadas para 10 m, sempre com “\~”.
- Todo rótulo traz sol e data: “sol 4643 (28/08/2025)”. Sol é o dia solar marciano (24 h 39 min); a contagem começa no pouso do Curiosity, em 06/08/2012.
- Só entram no painel imagens com posição exata de parada do rover (Navcam). A Mastcam, que vem sem posição, não aparece nele.
- Crédito visível em cada imagem: “NASA/JPL-Caltech” ou “NASA/JPL-Caltech/MSSS”.

**Escopo do MVP de sábado:** panoramas Navcam do boxwork georreferenciados, abertura orientada, fotos estáticas próximas (Navcam) e recorte HiRISE. O panorama colorido PIA26559 (Mastcam) fica fora do mapa e aparece só na abertura do pitch. **Só no pitch:** rover batedor alimentando o mesmo índice.

## Fontes que vamos usar

Todas são abertas, sem chave e funcionavam em 10/11/2026. Cada uma entra por um adaptador próprio, para que a fonte oficial da aba Resources a substitua na sexta sem mexer no resto.

| Fonte | O que nos dá | Papel na feature | Acesso |
| --- | --- | --- | --- |
| Panoramas cilíndricos Navcam (science.nasa.gov) | 360° em P&B por parada; sol, site, drive e azimute central no texto e no nome do arquivo | Conteúdo principal do clique | Página HTML por sol + PNG |
| PIA26559 (Photojournal JPL) | Primeiro 360° colorido do boxwork, Mastcam, 291 imagens | Imagem de abertura do pitch, sem posição no mapa | JPG grande, reduzir |
| Feed de imagens brutas do MSL | Sol, câmera, site, drive, `mast_az`, `mast_el`, link da imagem | Fotos estáticas próximas | JSON: `mars.nasa.gov/api/v1/raw_image_items/` |
| Waypoints MMGIS do MSL | Lat, lon, elevação e `yaw` por site/drive | Ponte para lat/lon | GeoJSON: `mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json` |
| PLACES (PDS Imaging) | 49.315 posições localizadas, inclusive drives intermediários, até 17/04/2026 | Validação e fallback de posição | CSV `localized_interp.csv` (11 MB) |
| Mosaico HiRISE colorido de Gale (USGS) | Imagem orbital de 25 cm/px ao longo do trajeto | Base do mapa e recorte do ponto | COG na AWS, recorte por janela |

**Fica de fora:** a Mars Rover Photos API (api.nasa.gov), arquivada em out/2025 e sem posição nem azimute. Se os Resources trouxerem só uma lista de fotos com sol e câmera, a posição continua vindo do MMGIS.

## Como os dados se casam

Nenhum panorama ou foto traz lat/lon diretamente. A chave que liga tudo é o par site/drive (a parada do rover), cruzado com os waypoints do MMGIS.

1. **Imagem → site/drive.** Panorama: lido do nome do arquivo. Em `N_R000_4643_EDR118CYLASB2028_AUTOLM1.PNG`, `4643` é o sol, `118` o site e `2028` o drive. Foto Navcam: campos `site` e `drive` do feed; se vierem nulos, o trecho `F1182028` do nome do arquivo. Foto Mastcam: vem sem site, drive, azimute e posição (confirmado na M1); por isso ela fica fora do banco de fotos próximas e serve só à ficha científica.
2. **Site/drive → lat/lon.** Busca exata da chave `RMC` (`"118_2028"`) no MMGIS. Sem resultado, busca no PLACES, que tem os drives intermediários.
3. **Lat/lon → distância e rumo** até o ponto informado, por haversine.
4. **Rumo → abertura do panorama:** `yaw_inicial = rumo_parada→ponto − azimute_central`, normalizado entre −180° e 180°.

**Conceitos que precisamos acertar:**

- **Latitude planetocêntrica.** É a usada pelo MMGIS e pelos tiles do Mars Trek. O PLACES também traz a planetodética, cerca de 3 km diferente no pouso. Nunca misturar.
- **Longitude leste positiva**, entre 0° e 360° (o boxwork fica perto de 137,4° E, 4,8° S).
- **Raio de Marte:** 3.396.190 m, a esfera Mars 2000 do Mars Trek, para o haversine bater com o mapa.
- **`yaw` do MMGIS** vem com sinal (ex.: −132,02°); normalizar com `(yaw + 360) % 360`.
- **Duas direções diferentes:** a direção do ponto até a parada do rover (“tirada a NE daqui”) e a direção para onde a câmera apontava (`mast_az`). Ainda não sabemos se `mast_az` é medido a partir do norte ou da frente do rover; a tarefa 6 resolve isso.

```latex
d = 2R \arcsin\sqrt{\sin^2\frac{\Delta\varphi}{2} + \cos\varphi_1 \cos\varphi_2 \sin^2\frac{\Delta\lambda}{2}}
```

## Arquitetura

Três peças, todas offline no notebook: um ETL que monta o pacote de dados, uma API local que responde ao clique e o frontend do mapa com o visualizador 360.

**Stack:** Python 3.11 + FastAPI + SQLite com R\*Tree (já embutido no SQLite) + Pillow; frontend Leaflet + Pannellum, com JS, CSS e tiles servidos localmente, sem CDN.

**Estrutura do repositório:**

```
h2g2-f03/
  config.yaml        # qual fonte usar: mock | public | official
  etl/               # sources/ (adaptadores), build.py, panos.py, photos.py
  api/               # main.py (FastAPI), geo.py (haversine, rumo)
  web/               # index.html, map.js, pano.js, lib/ (leaflet, pannellum)
  bundle/            # h2g2.db, panos/, img/, thumbs/, tiles/, MANIFEST.json
```

**Banco (`h2g2.db`):**

```sql
CREATE TABLE waypoints(rmc TEXT PRIMARY KEY, site INT, drive INT, sol INT,
  lat REAL, lon REAL, elev REAL, yaw REAL, source TEXT);
CREATE TABLE panoramas(id TEXT PRIMARY KEY, sol INT, site INT, drive INT,
  lat REAL, lon REAL, center_az REAL, haov REAL, vaov REAL, voffset REAL,
  img_path TEXT, page_url TEXT, credit TEXT, pos_quality TEXT);
CREATE TABLE photos(id TEXT PRIMARY KEY, instrument TEXT, sol INT, site INT, drive INT,
  date_taken TEXT, lat REAL, lon REAL, mast_az REAL, mast_el REAL,
  img_path TEXT, thumb_path TEXT, credit TEXT, pos_quality TEXT, source TEXT);
CREATE VIRTUAL TABLE pano_rtree  USING rtree(rid, min_lon, max_lon, min_lat, max_lat);
CREATE VIRTUAL TABLE photo_rtree USING rtree(rid, min_lon, max_lon, min_lat, max_lat);
```

**Endpoints da API local:**

| Endpoint | Resposta |
| --- | --- |
| `GET /panoramas/nearest?lat&lon&radius=300` | Panorama mais próximo, distância, rumo, `yaw_inicial` e rótulo pronto |
| `GET /photos/near?lat&lon&radius=200&limit=20` | Fotos ordenadas por distância, agrupadas por parada |
| `GET /orbital/crop?lat&lon` | PNG HiRISE de 100 × 100 m |
| `GET /health` | Fonte ativa e data do snapshot |

**Algoritmo de busca:** caixa em graus ao redor do ponto informado (`dlat = r/R × 180/π`, `dlon = dlat / cos(lat)`) → consulta na R-tree → haversine exato e filtro `d ≤ r` → ordenação por distância.

**Adaptadores de fonte:** o ETL só conversa com duas interfaces, `PanoSource`/`PhotoSource` (de onde vêm as imagens) e `PositionSource` (de onde vem a lat/lon). Implementações: `Mock`, `Public` (feed, science.nasa.gov, MMGIS, PLACES) e `Official` (escrita na sexta). Trocar de fonte = mudar o `config.yaml` e rodar o ETL de novo.

## Tarefas até quinta (12/11)

São 10 tarefas em três dias. A ordem importa: as tarefas 2, 4 e 6 destravam todo o resto e devem ficar prontas primeiro.

| Dia | Tarefas |
| --- | --- |
| Terça 10/11 (noite) | 1, 2, 3 |
| Quarta 11/11 | 4, 5, 6, 7 |
| Quinta 12/11 | 8, 9, 10 |

### 1. Montar o repositório e o contrato de dados

**Objetivo:** deixar pronta a estrutura que permite trocar mock por dado público e, na sexta, por dado oficial, sem reescrever a feature.

**Meio:** criar a estrutura de pastas da seção Arquitetura. Em `etl/sources/base.py`, definir as interfaces `PanoSource`, `PhotoSource` e `PositionSource` como `typing.Protocol`, cada uma com um único método (`list_panoramas(sol_min, sol_max)`, `list_photos(...)`, `locate(site, drive, sol)`). Definir os registros `PanoMeta`, `PhotoMeta` e `Position` como `dataclass`, com os mesmos campos das tabelas do banco. Criar o `config.yaml` com a chave de fonte e a janela de sols (4550 a 4845).

**Pronto quando:** `python etl/build.py --source mock` roda sem erro, mesmo com adaptadores vazios.

### 2. Congelar o trajeto do boxwork

**Objetivo:** ter as posições reais das paradas do Curiosity no boxwork, que dão lat/lon a panoramas e fotos e definem a área do mapa.

**Meio:** baixar `MSL_waypoints.json` com `requests` e salvar com a data no nome (`waypoints_2026-11-10.json`), porque o arquivo é atualizado a cada poucos dias. Filtrar as features com `sol` entre 4550 e 4845. Gravar na tabela `waypoints` os campos `RMC`, `site`, `drive`, `sol`, `lat`, `lon`, `elev_geoid` e `yaw` normalizado. Calcular o retângulo envolvente (lon/lat mínimas e máximas) e somar uma margem de 300 m: essa é a janela do mapa e do recorte HiRISE.

**Pronto quando:** a tabela tem as paradas do boxwork e o retângulo está anotado no `config.yaml`.

### 3. Validar posições com o PLACES

**Objetivo:** garantir que as coordenadas estão certas e ter fallback para drives que o MMGIS não lista.

**Meio:** baixar `localized_interp.csv` do PDS Imaging Node e carregar com `pandas`. Filtrar pela mesma janela de sols. Cruzar 10 pares site/drive com o MMGIS e conferir que a diferença é de poucos metros, usando a coluna `planetocentric_latitude`. Escrever o adaptador `PlacesPosition` como segundo passo da busca de posição. Criar um teste com o ponto de pouso (−4,58947° de latitude planetocêntrica).

**Pronto quando:** o teste passa e a diferença MMGIS × PLACES está registrada no `MANIFEST.json`.

### 4. Inventariar os panoramas do boxwork

**Objetivo:** ter a lista completa de panoramas Navcam da janela de sols, com sol, site, drive e azimute central. É o conteúdo principal da feature.

**Meio:** primeiro, testar se o feed de imagens brutas lista os mosaicos como produtos próprios: buscar no sol 4643 por nomes contendo `CYL`. Se listar, a coleta vira uma consulta paginada. Se não listar, coletar das páginas “Sol XXXX: Right Navigation Camera, Cylindrical Projection” do science.nasa.gov: um script com `requests` + `BeautifulSoup` lê o texto (site, drive, azimute central) e o link do PNG; se o scraping falhar, a coleta manual leva cerca de uma hora para 15 a 30 paradas. Gravar `panoramas.csv` com `sol, site, drive, center_az, png_url, page_url`. Usar o nome do arquivo como conferência: `EDR118CYLASB2028` deve bater com site 118 e drive 2028.

**Pronto quando:** o CSV cobre toda a janela de sols e a contagem de panoramas está anotada (ela define o quanto o mapa fica coberto).

### 5. Georreferenciar e preparar os panoramas

**Objetivo:** transformar cada panorama num arquivo leve, com posição e parâmetros prontos para o visualizador 360.

**Meio:** para cada linha do CSV, buscar lat/lon pela cadeia site/drive → MMGIS → PLACES. Baixar o PNG, reduzir para no máximo 8.000 px de largura com Pillow e salvar em `bundle/panos/`. Calcular o campo de visão vertical: numa projeção cilíndrica com o mesmo número de graus por pixel nos dois eixos, `vaov = 360 × altura ÷ largura`. Gravar `haov = 360`, `vaov` e `voffset = 0` (ajustado na tarefa 6). O PIA26559 colorido não entra nesta tabela: é usado só no pitch.

**Pronto quando:** a tabela `panoramas` está populada, cada um com lat/lon e `pos_quality`.

### 6. Visualizador 360 orientado (teste de validação)

**Objetivo:** provar o diferencial (o panorama abre olhando para o ponto clicado) e validar a referência de direção.

**Meio:** página de teste com Pannellum carregando o panorama do sol 4643 (site 118, drive 2028, azimute central 65°). Configuração: `type: "equirectangular"`, `haov: 360`, `vaov` e `vOffset` da tabela, `northOffset: center_az` e `yaw` igual ao `yaw_inicial` calculado. Escolher no HiRISE um alvo visível e reconhecível (uma crista ou o rastro do rover), ler a latitude e a longitude dele no mapa e informá-las na página de teste para conferir se o panorama abre virado para ele. Ajustar `vOffset` até o horizonte ficar reto. Com o mesmo panorama, comparar o `mast_az` de uma foto Navcam do mesmo sol para descobrir se ele é medido a partir do norte ou da frente do rover (nesse caso, direção = `(mast_az + yaw) % 360`).

**Pronto quando:** o panorama abre na direção certa, com erro menor que \~15°, e a referência do `mast_az` está anotada.

### 7. ETL das fotos estáticas

**Objetivo:** ter cerca de 200 fotos reais para a faixa abaixo do panorama, que também cobre pontos sem panorama.

**Meio:** consultar o feed de imagens brutas por sol, de 4550 a 4845, com `condition_2=4550:sol:gte&condition_3=4845:sol:lte`, 100 itens por página e `time.sleep(0.5)` entre requisições. Câmeras: `NAV_LEFT_B` e `NAV_RIGHT_B`. Amostrar até 2 fotos por parada, com azimutes diferentes. A Mastcam fica fora desta tabela: vem sem site, drive, azimute e posição (M1) e não casaria com o ponto digitado. Baixar cada JPG, gerar miniatura de 320 px com Pillow e posicionar pela cadeia da seção “Como os dados se casam”.

**Pronto quando:** a tabela `photos` tem cerca de 200 registros, cerca de 60 MB de imagens, e a R-tree está populada.

### 8. API local

**Objetivo:** responder ao ponto informado em milissegundos, sem internet.

**Meio:** em `api/geo.py`, as funções `haversine` e `bearing` com R = 3.396.190 m e o `yaw_inicial`. Em `api/main.py`, os quatro endpoints da seção Arquitetura, lendo o SQLite em modo somente leitura. Cada resposta traz o rótulo pronto (“panorama tirado a \~90 m daqui · sol 4643 (28/08/2025) · Navcam”). Servir `bundle/` como estáticos pela própria FastAPI.

**Pronto quando:** a latitude e a longitude de uma parada conhecida devolve o panorama dela a menos de 10 m.

### 9. Base orbital HiRISE offline e formulário de ponto (latitude e longitude)

**Objetivo:** ter o mapa do boxwork funcionando sem internet e simular, na versão final, o ponto clicado por meio de duas caixas de entrada. Latitude e longitude bastam: é tudo de que a API precisa para buscar o panorama, as fotos e o recorte.

**Meio:** em três partes.

1. **Base orbital.** Recortar só a janela da tarefa 2 do COG colorido da USGS, sem baixar o arquivo inteiro: `gdal_translate /vsicurl/<url do COG> -projwin ... boxwork.tif`. Gerar tiles com `gdal2tiles.py -p geodetic -z 14-19`. No Leaflet, usar `L.CRS.EPSG4326` e os tiles locais.
2. **Formulário de ponto.** Um painel com duas caixas numéricas, “Latitude (°)” e “Longitude (°E)”, e o botão “Buscar”. Ao enviar, o frontend chama `/panoramas/nearest` e `/photos/near` com esses dois valores, abre o Pannellum no painel lateral e lista as miniaturas embaixo.
3. **Mapa só de exibição.** Ele não recebe mais o clique: mostra o marcador na coordenada digitada, os ícones 360 das paradas e o trajeto do rover. Usar a mesma projeção e os mesmos tiles da feature 01, combinando com a Ingride.

**Regras do formulário:**

| Campo | Regra |
| --- | --- |
| Latitude (°) | Planetocêntrica, decimal, de −90 a 90. Fora da janela do boxwork (tarefa 2), avisar “ponto fora da área do mapa”. |
| Longitude (°E) | Leste positivo, decimal, de 0 a 360. Aceitar valor negativo e converter somando 360. |
| Pontos de exemplo | Botões opcionais que preenchem as caixas com coordenadas de paradas reais da tabela `waypoints` (por exemplo, a parada com panorama do sol 4643). Servem para a demo sem digitar. |

Não entram como campo: sol, câmera e raio. O sol e a câmera vêm do banco, e o raio fica fixo no `config.yaml` (300 m para panorama, 200 m para fotos).

**Pronto quando:** digitar a latitude e a longitude de uma parada conhecida abre o panorama dela, e o marcador aparece no lugar certo do mapa.

### 10. Pacote offline e teste sem internet

**Objetivo:** garantir que tudo roda no Colégio Perfil antes de a internet ser liberada.

**Meio:** rodar `build.py --source public` do zero e gerar o `MANIFEST.json` com fontes, URLs, datas do snapshot e créditos. Copiar Leaflet e Pannellum para `web/lib/`. Desligar o Wi-Fi e fazer o roteiro da demo: digitar as coordenadas de um vale entre cristas → panorama → fotos → recorte HiRISE. Copiar o pacote para um pendrive.

**Pronto quando:** o roteiro funciona do início ao fim com o Wi-Fi desligado.

## Tarefas manuais (sem código)

Doze tarefas se fazem no navegador, numa planilha, no QGIS ou no pendrive, sem abrir a IDE. Cada uma destrava uma tarefa técnica do plano. As três primeiras (M1, M2, M4) mostram o que é possível, então vêm antes de tudo.

| # | Tarefa manual | Destrava | Quando |
| --- | --- | --- | --- |
| M1 | Testar o feed de imagens no navegador | 7 | Terça 10/11 |
| M2 | Baixar waypoints e PLACES | 2, 3 | Terça 10/11 |
| M3 | Cruzar MMGIS × PLACES na planilha | 3 | Quarta 11/11 |
| M4 | Inventariar os panoramas | 4, 5 | Terça 10/11 |
| M5 | Baixar os PNGs dos panoramas | 5 | Quarta 11/11 |
| M6 | Validar a direção do `mast_az` na mão | 6 | Quarta 11/11 |
| M7 | Abrir o HiRISE no QGIS e anotar alvos | 6, 9 | Quarta 11/11 |
| M8 | Curar os alvos científicos no blog do Curiosity | 7 e feature 04 | Quinta 12/11 |
| M9 | Alinhar o contrato com a Ingride | 9 e sábado | Quinta 12/11 |
| M10 | Teste offline e pendrive | 10 | Quinta 12/11 |
| M11 | Receber e classificar os Resources | Sexta | Sexta 13/11 |
| M12 | Perguntas para os mentores | Sábado | Sábado 14/11, antes das 13h30 |

**Andamento em 11/11/2026:** M4, M5, M6, M7 e M8 concluídas, com os resultados registrados em cada seção. M1, M2 e M3 não foram tocadas nesta sessão; M9 a M12 seguem em aberto.

**Pendências abertas:**

1. **Sol 4741 no `panoramas.csv`:** o texto da página diz drive 82, o nome do arquivo diz drive 232 (`divergencia_nome`). Confirmado pelo MMGIS: `120_232` é do sol 4741 e `120_82`, do sol 4711, então o texto da página repetiu o drive antigo. **Corrigido no CSV em 11/11:** a linha agora é `120_232`, com o alerta mantido em `verificacao` (`drive_corrigido_pelo_nome`). A seleção das 72 imagens não mudou (o sol 4743 continua sendo o escolhido para essa parada).
2. **Alvos da M7:** conferir os 4 alvos na prévia e acrescentar um rastro do rover.
3. **Tarefa 6:** somar o yaw ao `mast_az` ao posicionar as fotos Navcam no panorama (resultado da M6).
4. **Conferência da M6:** a segunda das 3 fotos foi a menos conclusiva; a hipótese B é bem sustentada, mas não é medição exata.
5. **Tamanho real da área e cobertura de 300 m:** as 72 paradas ocupam só 264 m (L-O) × 672 m (N-S), e a janela do mapa tem ~0,86 × 1,26 km, bem menos que os "~3 × 3 km" do plano. Dentro da janela, 73% da área tem um panorama a até 300 m, 44% a até 200 m, 20% a até 100 m e 10% a até 50 m. Os outros 27% mostrariam "nenhum panorama a menos de 300 m". Decidir se o raio fica em 300 m e se as caixas de lat/lon são limitadas à janela.

### M1. Testar o feed de imagens no navegador

**Objetivo:** confirmar que a API responde hoje e que traz site, drive e azimute nas fotos do boxwork.

1. Cole no navegador a [consulta de exemplo (sol 4643, Navcam esquerda)](https://mars.nasa.gov/api/v1/raw_image_items?order=sol%20desc&per_page=3&page=0&condition_1=msl:mission&condition_2=4643:sol:eq&search=NAV_LEFT_B&extended=thumbnail::sample_type::noteq).
2. Se o JSON aparecer numa linha só, cole num formatador de JSON online ou use a extensão de formatação do navegador. São dados públicos, sem risco.
3. Nos itens, confira `"site": 118`, `"drive": 2028` e, dentro de `"extended"`, os campos `"mast_az"` e `"mast_el"`.
4. Na URL, troque `NAV_LEFT_B` por `MAST_LEFT` e veja se `site`, `drive` e `mast_az` vêm preenchidos ou `null`. Se não voltar nada, tente `MAST_RIGHT` ou apague o trecho `&search=...` e leia o campo `instrument` dos itens.
5. Repita o passo 4 trocando `4643` por `4600` e por `4700`.

**Deu certo quando:** você anotou, para cada sol testado, se a Mastcam traz site/drive. Isso confirma que a Mastcam fica fora do painel de fotos próximas.

### M2. Baixar waypoints e PLACES

**Objetivo:** ter as duas fontes de posição guardadas no computador, com a data do download.

1. Abra o [arquivo de waypoints do MMGIS](https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json), aperte Ctrl+S e salve como `waypoints_2026-11-10.json` (troque pela data do dia).
2. Abra o arquivo num editor de texto, busque `118_2028` e confira que existe uma parada com `lat`, `lon` e `sol`.
3. Baixe o [PLACES (localized\_interp.csv, 11 MB)](https://planetarydata.jpl.nasa.gov/img/data/msl/msl_places/data_localizations/localized_interp.csv) com Ctrl+S.
4. Abra o CSV no Excel ou no Google Sheets e filtre `site` = 118 e `drive` = 2028. Se houver mais de uma linha, anote o que muda entre elas na coluna `frame`.
5. Anote quantas linhas cada arquivo tem.

**Deu certo quando:** os dois arquivos abrem e a parada 118\_2028 existe nos dois.

### M3. Cruzar MMGIS × PLACES na planilha

**Objetivo:** garantir que as coordenadas batem e descobrir qual coluna de latitude usar.

1. Converta o JSON do MMGIS em tabela: abra-o no QGIS (passos da M7), vá em Exportar > Salvar feições como > CSV, ou use um conversor online de JSON para CSV.
2. Numa planilha, monte uma aba com 10 paradas do boxwork (sols 4550 a 4845) que existam nos dois arquivos. Colunas: site, drive, lat MMGIS, lon MMGIS, lat PLACES, lon PLACES.
3. Para a latitude do PLACES, use a coluna `planetocentric_latitude`.
4. Calcule a diferença em graus (`=ABS(lat MMGIS − lat PLACES)`) e converta para metros multiplicando por 59.276 (1° de latitude em Marte).
5. Confira que as duas longitudes estão em graus leste, perto de 137,4.
6. Teste de contraprova: refaça a conta com `planetodetic_latitude`. A diferença deve estourar para milhares de metros, o que confirma que a planetocêntrica é a coluna certa.

**Deu certo quando:** a diferença com a planetocêntrica é de poucos metros nas 10 paradas. Anote a maior diferença.

### M4. Inventariar os panoramas

**Objetivo:** montar a lista de panoramas Navcam da janela de sols 4550 a 4845. É o conteúdo principal da feature.

1. Abra a [página do panorama do sol 4643](https://science.nasa.gov/resource/sol-4643-right-navigation-camera-cylindrical-projection/) e leia sol, site, drive, azimute central e o link do PNG.
2. Comece a planilha com os panoramas já conhecidos: sols 4573, 4621, 4643 e 4709.
3. Para achar os outros, pesquise no Google `site:science.nasa.gov "Cylindrical Projection" "Navigation Camera"` somado a cada sol (por exemplo, `"Sol 4660"`), ou use a busca do próprio science.nasa.gov. Nem todo sol tem panorama.
4. Colunas da planilha: sol, site, drive, azimute central, nome do arquivo PNG, URL da página, câmera (esquerda ou direita), observação.
5. Confira cada linha: o nome do arquivo deve conter site e drive. Em `...EDR118CYLASB2028...`, 118 é o site e 2028 o drive. Se o nome divergir do texto da página, anote.
6. Conte as linhas.

**Deu certo quando:** a planilha cobre a janela de sols e o total está anotado. Se forem poucos panoramas, avise o time: o plano passa a dar mais peso às fotos estáticas.

**Resultado (11/11/2026), feito com `coletar_panoramas.py`:** 99 páginas de panorama nos sols 4552 a 4845, em 72 paradas distintas (`site_drive`). Todas são da câmera direita; nenhuma da esquerda apareceu. 78 linhas saíram sem alerta e 21 com alerta em `verificacao`: 20 são `nome_fora_do_padrao` (o nome do arquivo da NASA vem com `X` no lugar de `_`, mas site, drive e azimute vieram do texto e estão corretos) e 1 é uma divergência (ver pendências abaixo). Há lacunas sem panorama entre os sols 4693 e 4709 e entre 4757 e 4789.

### M5. Baixar os PNGs dos panoramas

**Objetivo:** ter os arquivos locais e as dimensões deles, necessárias para configurar o visualizador 360.

1. Em cada página da M4, abra a imagem em tamanho original e salve com clique direito > Salvar imagem como. Nome: `pano_<sol>_<site>_<drive>.png`.
2. Abra cada PNG e confira: é muito mais largo que alto, em preto e branco, sem cortes visíveis.
3. Veja largura × altura nas propriedades do arquivo e anote na planilha.
4. Opcional: baixe o [PIA26559, primeiro 360° colorido do boxwork](https://www.jpl.nasa.gov/images/pia26559-curiositys-first-360-degree-view-of-boxwork-patterns/). Ele não entra no mapa nem no banco: serve só para a abertura do pitch. É grande, então baixe a versão menor oferecida na página se a conexão for lenta.

**Deu certo quando:** a pasta tem todos os PNGs e a planilha tem largura e altura de cada um.

**Resultado (11/11/2026):** 72 PNGs em `dados_panoramas/panos/` (522 MB), um por parada, sem falhas de download. Todos têm largura e altura no CSV: larguras de 4.946 a 7.665 px (abaixo do teto de 8.000 px, então nenhum precisa ser reduzido) e `vaov` de 87° a 114°. O PIA26559 colorido foi baixado por você, fora do script.

### M6. Validar a direção do `mast_az` na mão

**Objetivo:** descobrir se `mast_az` é medido a partir do norte ou da frente do rover. É a mesma verificação da tarefa 6, feita sem código.

1. Abra o PNG do panorama do sol 4643 (centro em 65°).
2. Na API da M1, pegue 3 fotos Navcam da mesma parada (site 118, drive 2028), com azimutes diferentes. Anote `mast_az`, `mast_el` e o link de cada foto. Prefira fotos com `mast_el` entre −25° e 0°: as que olham muito para baixo (como −47°) podem não aparecer no panorama.
3. Para cada foto, calcule onde ela deveria cair no panorama, em % da largura: `50% + (azimute − 65) ÷ 360 × 100%`, com a diferença de azimute normalizada entre −180° e 180°. Faça a conta para duas hipóteses:
   - A, norte: azimute = `mast_az`.
   - B, frente do rover: azimute = `mast_az + 64,5°` (o yaw do rover nesse sol, tirado de uma imagem do mesmo sol), módulo 360.
4. Exemplo com `mast_az` = 350°: a hipótese A dá cerca de 29% da largura; a B dá cerca de 47%.
5. No PNG, vá até cada posição (a régua de qualquer visualizador de imagens serve) e veja qual delas mostra a cena da foto: rochas, crista, horizonte.

**Deu certo quando:** as 3 fotos caem na mesma hipótese. A hipótese A significa norte; a B, frente do rover. Anote o resultado no plano. Se nenhuma bater, avise o time antes de seguir.

**Resultado (10/11/2026): hipótese B — `mast_az` é medido a partir da frente do rover.** Azimute real = `mast_az + yaw`, módulo 360. Fotos da sequência `S1182028NCAM00266` (Navcam esquerda, sol 4643):

| Foto | `mast_az` | `mast_el` | A | B | O que bate no panorama |
|---|---|---|---|---|---|
| NLB_809682194 | 343,1° | −2,0° | 27% | 45% | B: morrinho escuro (~41%) e mesa em camadas à direita (~46–50%) |
| NLB_809682280 | 72,6° | −4,3° | 52% | 70% | B: crista clara no horizonte (~71–76%) |
| NLB_809682463 | 194,8° | −12,1° | 86% | 4% | B: caixa do rover embaixo e morro escuro no horizonte (~97–4%) |

### M7. Abrir o HiRISE no QGIS e anotar alvos

**Objetivo:** confirmar que o mosaico HiRISE cobre o boxwork, definir a janela do mapa e anotar as coordenadas dos pontos de exemplo.

1. Instale o QGIS (versão estável, qgis.org).
2. Camada > Adicionar camada > Adicionar camada raster. Em Tipo de fonte, escolha Protocolo: HTTP(S) e cole o link do COG colorido: `https://asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/Mars/MSL/MSL_Gale_HiRISE-LRGB_78quads_sharp_cog.tif`. Se não abrir, confirme o link na [página do mosaico no Astropedia](https://astrogeology.usgs.gov/search/map/mars_msl_gale_merged_orthophoto_mosaic_25cm). Se o QGIS pedir o sistema de coordenadas, escolha o geográfico de Marte (Mars 2000).
3. Camada > Adicionar camada vetorial e abra o JSON de waypoints da M2. Botão direito na camada > Filtro, e digite `"sol" >= 4550 AND "sol" <= 4845`.
4. Dê zoom nos pontos e confira se o HiRISE cobre todos. Anote as paradas que ficarem fora.
5. Abra a tabela de atributos, ordene por `lon` e por `lat` e anote os valores mínimo e máximo. Some uma margem de 0,005° (cerca de 300 m): essa é a janela do mapa.
6. Escolha de 3 a 5 alvos reconhecíveis (uma crista, uma depressão com areia, um rastro do rover). Passe o mouse sobre cada um e leia lon/lat na barra de status. Antes, valide o sistema: passe o mouse sobre uma parada do MMGIS e confira que a barra mostra as mesmas lat/lon da planilha.
7. Opcional, para evitar o `gdal_translate`: Raster > Extração > Recortar raster por extensão, usando a janela do passo 5, e salve como `boxwork.tif`.

**Deu certo quando:** você tem um print do HiRISE com os pontos, a janela anotada e a lista de alvos com nome, latitude e longitude. A lista serve para a tarefa 6 e para os botões de pontos de exemplo.

**Resultado (11/11/2026), feito por linha de comando (`rasterio`), sem o QGIS:**

- **Cobertura:** as 72 paradas dos sols 4550 a 4845 caem dentro do HiRISE; nenhuma ficou de fora.
- **Janela do mapa** (margem de 0,005°): lon 137,374117 a 137,388573; lat −4,815600 a −4,794270.
- **Sistema de coordenadas:** o COG usa projeção equiretangular, esfera de Marte 2000 (R = 3.396.190 m). Convertendo lon/lat de uma parada para metros, o resultado bate com o `easting`/`northing` do MMGIS (diferença de ~1 mm). Isso substitui a conferência com o mouse do passo 6.
- **Recorte (passo 7):** `dados/boxwork.tif`, 25 cm/px, 3.428 × 5.057 px, 42 MB.
- **Print:** `dados/m7_hirise_paradas.jpg`, com as paradas em amarelo e grade em px.
- **Alvos** (`dados/m7_alvos.csv`), escolhidos a olho na prévia, com margem de ~10 m:

| Alvo | lat | lon |
|---|---|---|
| Rede de cristas do boxwork (polígonos) | −4,806710 | 137,380565 |
| Mancha escura de areia (depressão) | −4,800168 | 137,377429 |
| Mesa clara em camadas (borda oeste) | −4,808554 | 137,376417 |
| Faixa escura de areia no vale a leste | −4,803114 | 137,382960 |

Falta o alvo "rastro do rover": as trilhas não aparecem na resolução da prévia.

### M8. Curar os alvos científicos no blog do Curiosity

**Objetivo:** escolher os alvos que viram ficha científica (feature 04) .

1. Abra o [blog do Curiosity, sols 4641 a 4648](https://science.nasa.gov/blog/curiosity-blog-sols-4641-4648-thinking-outside-and-inside-the-boxwork/) e navegue pelos posts vizinhos na lista de blogs do Curiosity em science.nasa.gov.
2. Para cada post entre os sols 4550 e 4845, anote numa planilha: sol, alvo citado, o que foi feito (perfuração, imagem, análise) e o site, se aparecer.
3. Marque de 8 a 10 alvos para a ficha científica, entre eles os pontos de perfuração, como o Nevado Sajama (sol \~4722). Para cada alvo, anote o link de uma foto Mastcam do mesmo sol: ela ilustra a ficha e não entra no mapa.

**Deu certo quando:** a tabela tem de 8 a 10 alvos, cada um com sol e link do post.

**Resultado (11/11/2026):** 58 posts do blog cobrem a janela (sols 4563 a 4851), lidos via API do WordPress do science.nasa.gov. Não há posts nos sols 4550–4562 nem nos 4763–4787 (conjunção solar). Da leitura saíram 385 candidatos, 305 deles com nome (`dados/m8_todos_candidatos.csv`). A curadoria final tem 10 alvos em `dados/m8_alvos.csv`, cada um com sol, faixa de sols, post(s), o que foi feito e uma foto Mastcam do mesmo sol:

| # | Alvo | Tipo | Sol ref. |
|---|---|---|---|
| 1 | Altadena | furo de perfuração, borda do boxwork | 4564 (inferido) |
| 2 | Volcán Peña Blanca | crista com camadas | 4591 |
| 3 | Mojo | hollow | 4643 |
| 4 | Monte Grande | hollow | 4702 (faixa 4675–4709) |
| 5 | Valle de la Luna | furo (44º) | 4693 |
| 6 | Nevado Sajama | furo (45º), crista | 4718 |
| 7 | Nevado Sajama2 | furo ao lado, SAM com TMAH | 4795 |
| 8 | Polígonos no hollow Monte Grande | feição | 4745 |
| 9 | Contato leste do boxwork | contato geológico | 4825 |
| 10 | Contato sul e saída do boxwork | contato com unidade de sulfato | 4842 |

Limites: (a) os posts quase nunca dão o sol exato de cada alvo; os sols acima vêm de legendas de imagem ou do plano, e a coluna `confianca_sol` diz a origem; (b) nenhum post cita site/drive, então o vínculo com o mapa é só por sol; (c) as fotos Mastcam são do mesmo sol, mas não conferi a olho se mostram o alvo (a do Monte Grande é do sol 4703); (d) os alvos 9 e 10 têm partes só planejadas nos posts. Sete dos dez caem no mesmo sol de uma parada com panorama (o Mojo, sol 4643, é a parada 118_2028 da M6); o Monte Grande fica sem panorama por estar numa lacuna.

### M9. Alinhar o contrato com a Ingride

**Objetivo:** garantir que as features 01 e 03 falam o mesmo idioma de coordenadas.

1. Envie a ela uma mensagem curta com a entrada da feature 03: latitude planetocêntrica em graus decimais, longitude leste positiva de 0 a 360, esfera de Marte com raio de 3.396.190 m.
2. Passe a janela do mapa anotada na M7.
3. Pergunte qual fonte de tiles e quais níveis de zoom a feature 01 usa. Eles devem ser os mesmos do nosso mapa.

**Deu certo quando:** ela confirmou por escrito o formato das coordenadas e os tiles.

### M10. Teste offline e pendrive

**Objetivo:** garantir que tudo roda no Colégio Perfil antes de a internet ser liberada.

1. Com o pacote pronto (tarefa 10), copie a pasta do projeto e a pasta `bundle/` para o notebook da demo e para um pendrive.
2. Desligue o Wi-Fi e desconecte qualquer cabo de rede.
3. Abra o app, digite as coordenadas de um ponto de exemplo e confira: o panorama abre, as fotos aparecem e o recorte HiRISE carrega.
4. Procure sinais de dependência online: mapa em branco, ícones quebrados ou campos que ficam carregando.
5. Confira espaço em disco, carregador e uma segunda cópia do pacote.

**Deu certo quando:** o roteiro da demo funciona do início ao fim com o Wi-Fi desligado.

### M11. Receber e classificar os Resources (sexta)

**Objetivo:** saber exatamente o que a organização liberou e o que continua vindo das fontes públicas.

1. Abra a aba Resources do desafio e copie todos os links numa planilha: item, link, formato, tamanho, licença.
2. Baixe tudo o que for arquivo na hora, enquanto a internet está boa, e guarde no pendrive.
3. Classifique cada item: lista de fotos só com sol e câmera; lista com site/drive; arquivos PDS com label (`.LBL`, `.IMG`); panoramas ou mosaicos; imagem orbital ou relevo; trajeto ou posições.
4. Abra um exemplo de cada tipo: o nome do arquivo ou a página traz site, drive ou azimute? O arquivo de posições tem latitude e longitude?
5. Anote o que não veio, principalmente posição e panoramas.

**Deu certo quando:** a planilha classificada está com quem vai escrever o adaptador `Official`, com a lista do que continua vindo das fontes públicas.

### M12. Perguntas para os mentores (sábado, antes das 13h30)

**Objetivo:** chegar com as dúvidas prontas para falar com o Emerson, mentor dos desafios espaciais, que inclui o Martian Map.

1. Escreva as perguntas num papel ou arquivo antes do sábado.
2. Perguntas sugeridas: os Resources trazem panoramas ou só imagens soltas? As fontes públicas (feed de imagens, MMGIS, PLACES) valem como complemento dos dados oficiais? Existe dado de posição para as imagens?
3. Anote as respostas e atualize o plano.

**Deu certo quando:** as respostas estão anotadas e o time sabe se o pacote público pode ficar.

## Sexta (13/11) e sábado (14/11)

Na sexta, a fonte oficial entra no lugar da pública, sem mexer na lógica. No sábado, a feature se liga às features 01 e 04.

**Sexta à noite, quando os Resources abrirem:**

- [ ] Ler a aba Resources e encaixar cada item num dos três formatos previstos: lista de fotos só com sol e câmera; lista com site/drive; arquivos PDS com label.
- [ ] Escrever o adaptador `Official` para o formato que vier. Se não houver posição, ela continua vindo do MMGIS e do PLACES.
- [ ] Se vierem panoramas, mosaicos, HiRISE ou modelo de relevo oficiais, trocar os nossos por eles e manter os públicos como reserva.
- [ ] Rodar `build.py --source official` e comparar contagens e posições com o pacote público.
- [ ] Gerar o pacote final e copiar para o pendrive.

**Sábado, integração:**

- [ ] Combinar com a Ingride que o contrato entre as features é só latitude e longitude: se o mapa da feature 01 estiver pronto, ele apenas preenche as duas caixas; se não, a demo roda pelo formulário. Mesma projeção e mesmos tiles.
- [ ] Ligar cada parada à ficha científica da feature 04 por sol e site: alvo estudado e trecho do blog do Curiosity.
- [ ] Ensaiar o roteiro da demo antes das 13h30, quando os mentores entram em campo. Levar a pergunta: os Resources trazem panoramas ou só imagens soltas?

## Riscos e pontos a validar

O maior risco é a cobertura: panoramas só existem nas paradas do rover, ao longo de uma linha, e não sobre toda a área. As fotos estáticas cobrem o resto.

| Risco | Mitigação |
| --- | --- |
| Poucos panoramas na janela do boxwork | Contagem na tarefa 4; mapa mostra os ícones 360 para guiar o clique; fotos como reserva |
| Feed raw ou MMGIS sai do ar ou muda de formato (são endpoints de site, sem documentação) | Cópia congelada com data até quinta; app 100% offline |
| Sem internet no local até sábado | Pacote completo no notebook e no pendrive; bibliotecas JS locais |
| Panorama abre na direção errada | Validação da tarefa 6 com alvo visível no HiRISE |
| Mastcam sem site, drive, azimute e posição (confirmado nos sols 4600 e 4643) | Mastcam fora do painel de fotos próximas; Navcam como única fonte de fotos com posição |
| Arquivos pesados (HiRISE de 23 GB, PIA26559 grande) | Recorte do COG só na janela; panoramas reduzidos para 8.000 px |
| Latitude planetodética misturada com planetocêntrica | Usar só planetocêntrica; teste com o ponto de pouso |

**Pontos ainda não confirmados:**

- Se o feed raw lista os mosaicos cilíndricos (tarefa 4).
- Se `mast_az` é medido a partir do norte ou da frente do rover (tarefa 6).
- Se a Navcam traz site e drive em todos os sols da janela 4550–4845 (conferir na tarefa 7).
- Quantos panoramas existem na janela de sols 4550–4845 (tarefa 4).

## Fontes

- [Feed de imagens brutas do MSL (exemplo, sol 4643)](https://mars.nasa.gov/api/v1/raw_image_items?order=sol%20desc&per_page=3&page=0&condition_1=msl:mission&condition_2=4643:sol:eq&search=NAV_LEFT_B&extended=thumbnail::sample_type::noteq)
- [Waypoints MMGIS do Curiosity](https://mars.nasa.gov/mmgis-maps/MSL/Layers/json/MSL_waypoints.json)
- [PLACES, localized\_interp.csv (PDS Imaging Node)](https://planetarydata.jpl.nasa.gov/img/data/msl/msl_places/data_localizations/localized_interp.csv)
- [Panorama Navcam do sol 4643 (site 118, drive 2028)](https://science.nasa.gov/resource/sol-4643-right-navigation-camera-cylindrical-projection/)
- [PIA26559, primeiro 360° do boxwork](https://www.jpl.nasa.gov/images/pia26559-curiositys-first-360-degree-view-of-boxwork-patterns/)
- [Mosaico ortorretificado HiRISE de Gale, 25 cm (USGS Astropedia)](https://astrogeology.usgs.gov/search/map/mars_msl_gale_merged_orthophoto_mosaic_25cm)
- [Sistemas de coordenadas do MSL (PDS)](https://pds-imaging.jpl.nasa.gov/documentation/MSL_COORDINATE_FRAMES.PDF)
- [Blog do Curiosity, sols 4641–4648 (boxwork)](https://science.nasa.gov/blog/curiosity-blog-sols-4641-4648-thinking-outside-and-inside-the-boxwork/)
- [Política de uso das imagens brutas da NASA](https://solarsystem.nasa.gov/raw-images/raw-images-faq/)
- [api.nasa.gov (Mars Rover Photos API arquivada)](https://api.nasa.gov/)
