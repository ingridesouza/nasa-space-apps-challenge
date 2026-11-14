# H2G2 · Feature 04 · Ficha científica do ponto — Plano de construção

Nov 13, 2026 · @vic

## O entregável decidido

O astronauta informa latitude e longitude (as mesmas duas caixas da feature 03) e o H2G2 abre um cartão estilo "pokédex" com o que já foi **medido** naquele lugar, por quem e com que confiança. A ficha nunca identifica mineral pela foto: ela cruza o que o Curiosity mediu no chão com o que os orbitadores veem de cima.

**O que o cartão traz, de cima para baixo:**

1. **Alvo mais próximo:** nome oficial do alvo (ex.: Mojo, Nevado Sajama), tipo (furo, crista, hollow, contato), sol e distância até o ponto ("\~40 m daqui").
2. **Medido no chão (Curiosity):** composição química (APXS/ChemCam) e mineralogia (CheMin) do alvo, com o resultado em uma frase e o instrumento.
3. **Visto de órbita (CRISM):** mineral dominante do pixel de \~18 m (sulfato, argila, nenhum sinal), com a ressalva de escala.
4. **Classe de terreno (AI4Mars):** solo, rocha-mãe, areia ou rocha grande, quando houver foto Navcam rotulada perto.
5. **Nome e contexto (IAU/USGS):** Monte Sharp, Cratera Gale, unidade geológica.
6. **Por que importa:** uma frase de habitabilidade/água subterrânea e uma de segurança (ex.: "areia nas depressões: risco de patinar").
7. **Rodapé:** nível de confiança, fonte de cada linha com link e crédito da foto Mastcam ilustrativa.

**Regras de honestidade da ficha:**

- Cada linha mostra a fonte e o instrumento. Sem fonte, a linha não aparece.
- Três níveis de confiança: **medido** (Curiosity no alvo), **inferido de órbita** (CRISM, \~18 m/px) e **contexto** (blog, nomenclatura).
- Se o ponto estiver longe de qualquer alvo (> 150 m), a ficha diz "nenhum alvo estudado a menos de 150 m" e mostra só órbita e terreno.
- O vínculo alvo → parada é por sol (o blog não cita site/drive). A ficha avisa: "posição aproximada pela parada do sol 4643".

**Escopo:** MVP de sábado com os 10 alvos curados na M8 (`dados/m8_alvos.csv`), mineralogia CRISM pré-calculada para a janela do boxwork e classe de terreno quando houver. Fica para o pitch: alvos novos reportados pelo astronauta por voz (feature 10) e a ficha lida em voz alta pelo assistente (feature 08).

**Itens avaliados que a ficha cobre:** Contexto científico (principal), Integração científica (chão + órbita no mesmo cartão), Uso de dados abertos (cada linha com fonte NASA) e Segurança operacional (frase de risco do terreno).

## Fontes oficiais

A ficha já pode ser montada só com dado oficial da NASA: o PDS publicou em 03/08/2026 a Release 42 do Curiosity, com APXS, ChemCam e CheMin dos sols 4710 a 4843, o coração do boxwork. A aba Resources do desafio ainda não foi conferida: o site do Space Apps bloqueia leitura automática, e as listas oficiais abrem hoje, 13/11. A tarefa M1 abaixo confere a aba e marca a coluna "Na aba Resources?".

**Achado que muda o plano da M8:** os nomes de arquivo do APXS trazem sol, site e drive ([SIS do APXS](https://pds-geosciences.wustl.edu/msl/msl-m-apxs-4_5-rdr-v1/mslapx_1xxx/document/apxs_rdr_sis.htm)), e os do ChemCam trazem site e drive no trecho `f<site><drive>`. Isso dá posição exata de parada aos alvos, que a M8 só ligava por sol.

| Fonte | Mantenedor | O que traz | Uso na ficha | Cobertura do boxwork | Na aba Resources? |
| --- | --- | --- | --- | --- | --- |
| [APXS RDR](https://pds-geosciences.wustl.edu/missions/msl/apxs.htm) (produto RWP) | PDS Geosciences / Agência Espacial Canadense | Óxidos em % de peso por alvo tocado pelo braço | Linha "Medido no chão: química" | Release 42: sols 4710–4843 | a conferir |
| [ChemCam LIBS RDR](https://pds-geosciences.wustl.edu/missions/msl/chemcam.htm) (MOC + lista mestre `msl_ccam_obs.csv`) | PDS Geosciences / LANL e CNES | Composição em óxidos por ponto de laser, alvo e sol | Química de cristas e alvos sem contato do braço | Sols 4613–4843 (inclui 4613–4709, antes inéditos) | a conferir |
| [CheMin RDR](https://pds-geosciences.wustl.edu/missions/msl/chemin.htm) (abundância mineral) | PDS Geosciences / NASA Ames | Minerais e % por amostra perfurada | Linha "Medido no chão: mineralogia", só nos furos | Release 42: sols 4710–4843 | a conferir |
| [MSL Analyst's Notebook](https://an.rsl.wustl.edu/msl/) | PDS Geosciences | Alvos, observações e instrumentos por sol e local | Validar alvo → sol → site/drive da M8 | Dados até o sol 4843 | a conferir |
| CRISM MTRDR via [Orbital Data Explorer](https://ode.rsl.wustl.edu/mars/) | PDS Geosciences / MRO | Mapas de minerais de órbita (sulfatos, argilas), \~18 m/px | Linha "Visto de órbita" | A verificar por busca na janela do boxwork | a conferir |
| PLACES e MMGIS (já no `h2g2.db` da F03) | PDS Imaging / JPL | Lat/lon de cada parada | Posição do alvo no mapa | 72 paradas da janela | a conferir |
| Imagens brutas Mastcam (feed do MSL) | JPL / MSSS | Foto colorida do alvo | Ilustração da ficha, com crédito | Uma por alvo na M8 | a conferir |
| [Gazetteer IAU/USGS](https://planetarynames.wr.usgs.gov/) | USGS / IAU | Nomes oficiais de feições | Nome e contexto (Aeolis Mons, Gale) | Só nomes regionais | a conferir |

**Atenção com nomes:** Mojo, Nevado Sajama e os demais alvos são nomes informais dados pela equipe do rover. A ficha os rotula como "nome do alvo (equipe Curiosity)" e reserva "nome oficial IAU" para Aeolis Mons e Gale.

**Se a aba Resources trouxer fontes diferentes:** cada linha acima entra por um adaptador próprio, como na F03. Item oficial que cubra a mesma linha substitui o público; o público fica de reserva.

## Fontes extraoficiais e complementares

As fontes abaixo dão contexto e narrativa, mas nenhuma linha "medido" da ficha depende delas. Elas entram como "contexto" no rodapé de confiança.

| Fonte | Tipo | Uso na ficha | Limite |
| --- | --- | --- | --- |
| Blog do Curiosity (science.nasa.gov), já curado na M8 | NASA, narrativo | "O que foi feito" e "por que importa" de cada alvo | Quase nunca dá o sol exato do alvo |
| [Notícia NASA sobre o boxwork](https://www.nasa.gov/missions/mars-science-laboratory/curiosity-rover/NASAs-curiosity-rover-sees-martian-spiderwebs-up-close/) (fev/2026) | NASA, divulgação | Frase-resumo: argila nas cristas, carbonato nas depressões, nódulos | Texto de divulgação, sem números |
| [Photojournal](https://science.nasa.gov/photojournal/search/) (nódulos no boxwork, 360° de Nevado Sajama) | NASA, imagem processada | Foto de destaque de 2 a 3 fichas | Sem posição de parada |
| [Fraeman et al. 2016](https://pmc.ncbi.nlm.nih.gov/articles/PMC5101845) e trabalhos sobre sulfatos de Mg em Gale ([EGU23](https://meetingorganizer.copernicus.org/EGU23/EGU23-16728.html)) | Artigos científicos | Base da frase "visto de órbita" e da unidade geológica | Mapas em figura, não em arquivo pronto |
| AI4Mars (JPL, 2021) | Dataset de rótulos de terreno | Pitch: classificador de terreno treinado nele | Publicado em 2021, antes do boxwork (2025): não há rótulo das fotos da janela |
| [Space Data Atlas](https://spacedata.swapniltamse.com/challenges/martian-map/) | Agregador independente, sem vínculo com a NASA | Código pronto de busca CRISM no ODE | Diz que as listas oficiais abrem em 13/11; não é a lista oficial |
| Repositórios de outros times ([ARIADNE](https://github.com/vyom-aggarwal/ARIADNE)) | Concorrentes | Referência de abordagem | ARIADNE também usa tabelas de alvos do ChemCam e os furos do boxwork: Gale não está livre de concorrência |

**Decisão para a classe de terreno no MVP:** rótulo curado à mão nos 10 alvos (crista, hollow, areia, contato), tirado do blog e das fotos, marcado como "classificação da equipe H2G2". O AI4Mars fica para o pitch.

## Como os dados se casam

A chave continua sendo o par site/drive, a mesma da F03: o alvo herda a lat/lon da parada de onde o rover o mediu. A diferença é que agora o site/drive vem do próprio arquivo de ciência, não só do sol.

1. **Alvo → sol:** vem da M8 (`dados/m8_alvos.csv`, coluna de sol e `confianca_sol`).
2. **Sol → site/drive:** listar os arquivos APXS e ChemCam daquele sol no PDS. No APXS, o nome `APA_<sclk>RWP<sol><site><drive>_P1.CSV` dá o site/drive. No ChemCam, o trecho `f<site><drive>` do nome dá o mesmo; a lista mestre `msl_ccam_obs.csv` liga arquivo a nome de alvo. Se o label não trouxer o nome do alvo, casar por sol e conferir no Analyst's Notebook.
3. **Site/drive → lat/lon:** busca exata da chave `RMC` na tabela `waypoints` do `h2g2.db` da F03; sem resultado, PLACES. A posição gravada é a da parada, não a do alvo.
4. **Ponto informado → alvo:** haversine (o `api/geo.py` da F03) até cada alvo; vence o mais próximo num raio de 150 m.
5. **Ponto informado → órbita:** leitura do pixel CRISM pré-processado naquela lat/lon e tradução em rótulo (sulfato monoidratado, sulfato poli-hidratado, argila Fe/Mg, sem sinal).
6. **Ponto informado → terreno:** polígonos curados à mão sobre o HiRISE (areia, crista, hollow), num GeoJSON que a rota da F02 também pode usar como custo.

**Incerteza de posição por instrumento:**

| Instrumento | Distância típica rover → alvo | Rótulo na ficha |
| --- | --- | --- |
| APXS, CheMin (braço, furo) | poucos metros | "medido nesta parada" |
| ChemCam (laser a distância) | até \~7 m | "medido a até \~7 m desta parada" |
| CRISM (órbita) | pixel de \~18 m | "média de uma área de \~18 m" |

**Convenções herdadas da F03, sem mudança:** latitude planetocêntrica, longitude leste de 0 a 360, esfera de 3.396.190 m.

## Arquitetura

A F04 entra dentro do `h2g2-f03/`, sem repositório novo: mesmo ETL, mesmo `h2g2.db`, mesma FastAPI e o card da UI-8, que hoje só tem layout. São três tabelas e um endpoint a mais.

**O que muda no repositório:**

```
h2g2-f03/
  config.yaml          # + science_source: mock | public | official ; + card_radius_m: 150
  etl/sources/         # + ScienceSource, OrbitalMineralSource (Protocol)
  etl/science.py       # APXS, ChemCam, CheMin -> measurements
  etl/targets.py       # m8_alvos.csv + site/drive -> targets
  etl/crism.py         # recorte CRISM -> bundle/crism_boxwork.tif
  api/main.py          # + GET /science/card
  web/card.js          # preenche o card da UI-8
  bundle/              # + crism_boxwork.tif, terrain.geojson, mastcam/
```

**Tabelas novas no `h2g2.db`:**

```sql
CREATE TABLE targets(id TEXT PRIMARY KEY, name TEXT, kind TEXT, sol INT,
  site INT, drive INT, lat REAL, lon REAL, pos_quality TEXT,
  why_it_matters TEXT, safety_note TEXT, blog_url TEXT,
  mastcam_path TEXT, mastcam_credit TEXT, terrain_class TEXT);
CREATE TABLE measurements(id TEXT PRIMARY KEY, target_id TEXT, instrument TEXT,
  sol INT, site INT, drive INT, summary TEXT, values_json TEXT,
  confidence TEXT, source_url TEXT, source_file TEXT);
CREATE VIRTUAL TABLE target_rtree USING rtree(rid, min_lon, max_lon, min_lat, max_lat);
```

**Endpoint:**

| Endpoint | Resposta |
| --- | --- |
| `GET /science/card?lat&lon` | Alvo mais próximo (ou vazio), distância, medições por instrumento, rótulo CRISM do pixel, classe de terreno, frases de contexto e segurança, fontes |

**Adaptadores:** `ScienceSource.list_measurements(sol_min, sol_max)` com implementações `Mock` (os 10 alvos com valores de exemplo), `Public` (PDS Release 42 e anteriores) e `Official` (escrita se a aba Resources trouxer algo). `OrbitalMineralSource.sample(lat, lon)` lê o raster local. Trocar de fonte continua sendo mudar o `config.yaml` e rodar o ETL.

## Tarefas de código

São 9 tarefas entre sexta à noite e sábado às 23h. As tarefas 1 e 2 destravam o resto e precisam estar prontas antes de o time chegar ao Colégio Perfil; a 5 (CRISM) tem limite de 2 horas, porque tem plano B.

| Quando | Tarefas |
| --- | --- |
| Sexta 13/11, noite | 1, 2 |
| Sábado 14/11, manhã (até 13h30) | 3, 4, 5 |
| Sábado 14/11, tarde | 6, 7, 8 |
| Sábado 14/11, noite (até 23h) | 9 |

### 1. Contrato e mock da ficha

**Objetivo:** ter o card funcionando de ponta a ponta com dados de exemplo, para a UI não esperar o ETL.

**Meio:** criar `targets` e `measurements` no `h2g2.db`, os Protocols `ScienceSource` e `OrbitalMineralSource` e o `MockScienceSource` com os 10 alvos da M8 e valores de exemplo marcados `confidence = "mock"`. Rotear `GET /science/card` lendo do banco.

**Pronto quando:** as coordenadas da parada 118\_2028 devolvem a ficha do Mojo com valores de exemplo.

### 2. Inventário do PDS do boxwork

**Objetivo:** saber exatamente quais medições existem em cada sol da janela 4550–4845.

**Meio:** baixar a lista mestre do ChemCam (`document/msl_ccam_obs.csv` do volume RDR) e a listagem de arquivos RWP do APXS. Filtrar pela janela de sols e extrair site/drive dos nomes. Gravar `dados/science_index.csv` com `sol, site, drive, instrumento, alvo, arquivo, url`. Para o CheMin, listar as amostras de abundância mineral do mesmo período.

**Pronto quando:** o índice cobre a janela e a contagem por instrumento está anotada no `MANIFEST.json`.

### 3. Alvos com posição exata

**Objetivo:** dar a cada um dos 10 alvos a lat/lon da parada onde foi medido.

**Meio:** cruzar `m8_alvos.csv` com `science_index.csv` por nome de alvo e sol. Com site/drive em mãos, buscar a chave `RMC` na tabela `waypoints`. Gravar `pos_quality = "exata"` quando o nome bate e `"por_sol"` quando só o sol bate.

**Pronto quando:** os 10 alvos estão em `targets`, cada um com `pos_quality`, e a R-tree está populada.

### 4. Medições do chão (APXS, ChemCam, CheMin)

**Objetivo:** transformar os arquivos do PDS em uma frase por instrumento, com o número que a sustenta.

**Meio:** ler o RWP do APXS (óxidos em %), o MOC do ChemCam (óxidos maiores por ponto, média por alvo) e a abundância mineral do CheMin nos furos. Gerar `summary` por regra fixa: os 3 óxidos mais altos e os destaques de enxofre e cálcio (sinais de sulfato). Guardar os valores completos em `values_json` e o link do arquivo em `source_url`.

**Pronto quando:** cada alvo com medição tem pelo menos uma linha "medido", e cada frase bate com o arquivo de origem numa conferência de 3 alvos.

### 5. Mineralogia de órbita (CRISM), limite de 2 horas

**Objetivo:** responder "o que se vê de cima neste ponto".

**Meio:** buscar no Orbital Data Explorer produtos CRISM MTRDR na janela do boxwork (lon 137,374117 a 137,388573; lat −4,815600 a −4,794270). Se houver, recortar os parâmetros de sulfato e argila, reprojetar na esfera de Marte e salvar `bundle/crism_boxwork.tif`, com um rótulo por pixel. Se não houver cobertura em 2 horas, a linha da ficha passa a dizer "unidade de sulfatos de Mg vista de órbita na região (Fraeman et al. 2016)", marcada como contexto.

**Pronto quando:** qualquer ponto da janela devolve um rótulo CRISM ou o texto de contexto, nunca vazio.

### 6. Classe de terreno

**Objetivo:** dizer se o ponto é crista, hollow ou areia, e o risco disso.

**Meio:** desenhar no QGIS, sobre o `boxwork.tif`, 10 a 20 polígonos a partir dos alvos da M7 (manchas de areia, rede de cristas). Exportar `bundle/terrain.geojson` com `classe` e `nota_seguranca`. Consulta por ponto-no-polígono com Shapely. Combinar com o Hugo: o mesmo arquivo vira custo de areia na rota da F02.

**Pronto quando:** os 4 alvos da M7 caem na classe certa.

### 7. Endpoint da ficha

**Objetivo:** montar a resposta completa em milissegundos, offline.

**Meio:** `GET /science/card?lat&lon` busca o alvo mais próximo em 150 m pela R-tree, junta medições, rótulo CRISM e classe de terreno, e devolve as linhas já com rótulo de confiança e fonte. Sem alvo no raio: devolve só órbita e terreno, com a mensagem "nenhum alvo estudado a menos de 150 m".

**Pronto quando:** os três casos (alvo perto, alvo longe, fora da janela) respondem certo.

### 8. Card na interface

**Objetivo:** ligar o card da UI-8 aos dados reais.

**Meio:** `web/card.js` chama `/science/card` junto com `/panoramas/nearest` e `/photos/near`. Ícone por tipo de alvo, selo de confiança por linha (medido, órbita, contexto), link da fonte e crédito da foto Mastcam. Estados carregando, vazio e erro, como nas outras seções.

**Pronto quando:** o card abre com dados reais nos 3 pontos de demo e nenhum campo mostra `null`.

### 9. Pacote offline e roteiro de demo

**Objetivo:** garantir que a ficha roda sem internet e cabe no tour de 3 minutos.

**Meio:** rodar o ETL do zero com `--source public`, atualizar o `MANIFEST.json` com as fontes da F04, copiar as fotos Mastcam para `bundle/mastcam/`. Escolher 3 pontos de demo: Mojo (hollow, parada 118\_2028, com panorama), Nevado Sajama (furo com CheMin) e uma mancha de areia sem alvo próximo. Testar com o Wi-Fi desligado.

**Pronto quando:** o roteiro dos 3 pontos funciona sem internet.

## Tarefas manuais (sem código)

Sete tarefas no navegador, numa planilha ou no QGIS. A M1 vem antes de tudo: ela diz se alguma fonte oficial do desafio substitui as públicas.

| # | Tarefa | Destrava | Quando |
| --- | --- | --- | --- |
| M1 | Abrir e classificar a aba Resources | Coluna "Na aba Resources?" e adaptador `Official` | Sexta 13/11, assim que abrir |
| M2 | Conferir 3 alvos no Analyst's Notebook | 2, 3 | Sexta 13/11, noite |
| M3 | Buscar CRISM no Orbital Data Explorer | 5 | Sexta 13/11, noite |
| M4 | Escrever "por que importa" e "nota de segurança" dos 10 alvos | 1, 7 | Sábado 14/11, manhã |
| M5 | Conferir se as fotos Mastcam mostram o alvo | 8 | Sábado 14/11, manhã |
| M6 | Desenhar os polígonos de terreno no QGIS | 6 | Sábado 14/11, manhã |
| M7 | Perguntas para o Emerson | Sábado | Sábado 14/11, antes das 13h30 |

### M1. Abrir e classificar a aba Resources

1. Abrir a aba Resources do desafio e copiar todos os links numa planilha: item, link, formato, licença.
2. Marcar os que tocam a ficha: dados do Curiosity (APXS, ChemCam, CheMin, Analyst's Notebook), CRISM, nomenclatura.
3. Preencher a coluna "Na aba Resources?" da seção de fontes oficiais deste documento.

**Deu certo quando:** cada linha da tabela de fontes oficiais tem "sim" ou "não".

### M2. Conferir 3 alvos no Analyst's Notebook

1. Abrir o [MSL Analyst's Notebook](https://an.rsl.wustl.edu/msl/) e ir aos sols 4643 (Mojo), 4693 (Valle de la Luna) e 4718 (Nevado Sajama).
2. Para cada um, anotar site, drive, instrumentos usados e nome do alvo como aparece no Notebook.
3. Conferir se o site/drive bate com a parada da tabela `waypoints`.

**Deu certo quando:** os 3 alvos têm site/drive confirmado. Se o nome no Notebook diferir do blog, anotar os dois.

### M3. Buscar CRISM no Orbital Data Explorer

1. Abrir o [Orbital Data Explorer](https://ode.rsl.wustl.edu/mars/), Map Search, instrumento CRISM.
2. Desenhar a janela do boxwork (lon 137,374117 a 137,388573; lat −4,815600 a −4,794270).
3. Anotar os IDs de produtos MTRDR (alvo, \~18 m/px) que cobrem a janela. Se não houver nenhum, anotar os de modo mapping mais próximos.

**Deu certo quando:** há uma lista de IDs ou a confirmação de que não há cobertura targeted (aciona o plano B da tarefa 5).

### M4. Frases dos 10 alvos

1. Para cada alvo da M8, escrever duas frases curtas: "por que importa" (água, habitabilidade) e "nota de segurança" (areia, crista, declive).
2. Só usar fatos do blog, da notícia NASA ou do PDS, com o link ao lado.

**Deu certo quando:** as 20 frases estão em `m8_alvos.csv`, cada uma com link.

### M5. Conferir as fotos Mastcam

1. Abrir a foto Mastcam de cada alvo (já listada na M8) e o post do blog.
2. Marcar "mostra o alvo" ou "só do mesmo sol". Fechar a pendência (c) da M8.

**Deu certo quando:** os 10 alvos têm a marcação. Foto "só do mesmo sol" aparece com essa legenda.

### M6. Polígonos de terreno no QGIS

1. Abrir `dados/boxwork.tif` e criar uma camada de polígonos com os campos `classe` e `nota_seguranca`.
2. Desenhar de 10 a 20 polígonos a partir dos alvos da M7: manchas escuras de areia, rede de cristas, mesa clara.
3. Exportar como `terrain.geojson` em graus (Mars 2000).

**Deu certo quando:** o arquivo abre no mapa sobre o HiRISE e o Hugo confirmou que serve para a F02.

### M7. Perguntas para o Emerson

1. Os Resources trazem dados de instrumentos do rover (APXS, ChemCam, CheMin) ou só orbitais?
2. Uma ficha que cruza medição do rover com CRISM conta como integração científica?
3. Fontes do PDS fora da aba Resources são aceitas como complemento?

**Deu certo quando:** as respostas estão anotadas e o time sabe se a ficha mantém as fontes públicas.

## Integração de sábado

O contrato entre as features continua sendo só latitude e longitude: quem informa o ponto (mapa da F01 ou caixas da F03) dispara as três buscas ao mesmo tempo.

| Feature | O que a F04 recebe | O que a F04 entrega | Combinar com |
| --- | --- | --- | --- |
| 01 · Mapa em camadas | Ponto clicado; mesma projeção e tiles | Ícones dos 10 alvos no mapa, por tipo | Ingride |
| 02 · Rota inteligente | Paradas da rota | `terrain.geojson` como custo de areia; alvos para a rota "mais ciência" | Hugo |
| 03 · Panorama no ponto | Parada mais próxima e seu sol | Card abaixo do panorama; Mojo liga as duas na demo | Victoria (já pronta) |

- [ ] Confirmar com a Ingride que os ícones de alvo usam a mesma camada de pontos das paradas.
- [ ] Entregar ao Hugo o `terrain.geojson` e a lista de alvos com lat/lon até as 13h30.
- [ ] Ensaiar o roteiro de 3 pontos (Mojo, Nevado Sajama, mancha de areia) junto com o panorama da F03.
- [ ] Pitch, se houver tempo: o assistente de voz (F08) lê a ficha em voz alta, sempre com fonte e nível de confiança.

## Riscos e pontos a validar

O maior risco é de conteúdo, não de código: uma frase científica errada na ficha custa mais diante da banca do que um campo vazio. Por isso toda frase sai de regra fixa ou de texto com link.

| Risco | Mitigação |
| --- | --- |
| Frase científica errada ou exagerada | Resumo por regra fixa (3 óxidos + destaques), conferência manual de 3 alvos, link para o arquivo |
| Sem CRISM targeted sobre o boxwork | Limite de 2 h na tarefa 5; linha vira contexto citando Fraeman et al. 2016 |
| Alvo da M8 sem medição no PDS (alvos só planejados nos posts, como 9 e 10) | Ficha mostra só contexto e órbita, com "sem medição publicada" |
| Nome do alvo diferente entre blog e PDS | M2 anota os dois; a ficha mostra o nome do PDS |
| Aba Resources com fonte equivalente | Adaptador `Official` substitui a linha; público fica de reserva |
| Outro time (ARIADNE) também no boxwork | Diferencial: ficha com nível de confiança por linha e ligação direta com o panorama da F03 |
| PDS fora do ar no sábado | Arquivos baixados na sexta; ETL roda offline |

**Pontos ainda não confirmados:**

- Se os sols 4550–4709 do APXS e do CheMin estão em releases anteriores à 42 (a página do ChemCam confirma 4613–4843; a do APXS e do CheMin só citam 4710–4843).
- Se o label do APXS traz o nome do alvo (tarefa 2).
- Se há CRISM MTRDR cobrindo a janela (M3).
- O que a aba Resources traz (M1).

## Fontes

- [PDS Geosciences · MSL APXS](https://pds-geosciences.wustl.edu/missions/msl/apxs.htm) e [SIS do APXS RDR](https://pds-geosciences.wustl.edu/msl/msl-m-apxs-4_5-rdr-v1/mslapx_1xxx/document/apxs_rdr_sis.htm)
- [PDS Geosciences · MSL ChemCam](https://pds-geosciences.wustl.edu/missions/msl/chemcam.htm)
- [PDS Geosciences · MSL CheMin](https://pds-geosciences.wustl.edu/missions/msl/chemin.htm)
- [Analyst's Notebook](https://an.rsl.wustl.edu/) (MSL até o sol 4843)
- [Orbital Data Explorer](https://ode.rsl.wustl.edu/mars/)
- [Gazetteer of Planetary Nomenclature (USGS/IAU)](https://planetarynames.wr.usgs.gov/)
- [NASA: Curiosity e o boxwork](https://www.nasa.gov/missions/mars-science-laboratory/curiosity-rover/NASAs-curiosity-rover-sees-martian-spiderwebs-up-close/)
- [Fraeman et al. 2016, estratigrafia de Mt. Sharp por órbita](https://pmc.ncbi.nlm.nih.gov/articles/PMC5101845)
- [Space Data Atlas · Martian Map](https://spacedata.swapniltamse.com/challenges/martian-map/) (independente, não oficial)
- [ARIADNE](https://github.com/vyom-aggarwal/ARIADNE) (repositório concorrente)
- Plano da F03 (`plano_acao.md`) e resultados da M7 e M8 no Project knowledge
