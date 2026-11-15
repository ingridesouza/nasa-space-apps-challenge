# Feature 01 · Camada "Sol direto e sombra" (inferida)

## O que faz

Para um sol e uma hora solar local, pinta o recorte do boxwork com a incidência do Sol direto e marca as sombras:
- **Posição do Sol:** Mars24 (`api/mars_time.py`).
- **Incidência:** inclinação e orientação do DTM HiRISE (1 m nativo, reduzido a 2 m).
- **Sombra de perto:** caminhada na direção do Sol sobre o mesmo DTM.
- **Sombra de longe:** horizonte do MOLA regional, para o Monte Sharp fora do recorte.

Código em `api/insolation.py`, endpoint `/api/insolation`, tiles em `/tiles/insolation/...?hour=`. O relógio é simulado (`H2G2_CLOCK="SOL@HH:MM"`, endpoint `/api/clock`). Os atalhos "agora" e "chegada" usam o tempo de ida da rota.

## Validação contra uma foto real (14/11/2026)

Teste: prever a luz e a sombra no instante em que a HiRISE fotografou o recorte e comparar com a própria foto.

- **Observação:** PSP_009294_1750, de 20/07/2008, Ls 101,3°, hora solar 15,43, incidência 58,0°, emissão 2,3°.
- **Leitura:** só o recorte, a 2 m, por `/vsicurl/` sobre o JP2 RED do PDS. Nada foi guardado no repositório.

| Teste | Sol real da foto | Controle: Sol oposto | Controle: girado 90° | Controle: 09h30 |
|---|---|---|---|---|
| Posição do Sol: modelo × metadado (4 observações) | diferença ≤ 0,1° | — | — | — |
| Correlação brilho da foto × incidência prevista, 2 m | **+0,33** | −0,30 | −0,17 | −0,21 |
| Correlação brilho da foto × incidência prevista, 10 m | **+0,38** | −0,35 | −0,19 | −0,24 |
| Sombras previstas que estão escuras na foto, sem tolerância | 11% | 2% | — | — |
| Sombras previstas que estão escuras na foto, tolerância de 4 m | 25% | 8% | — | — |
| Pixels escuros da foto que o modelo previu como sombra | ~0% | ~1% | — | — |

Nas linhas de sombra, "escuro" quer dizer escuro em relação à vizinhança de 50 m, para tirar o efeito da cor da rocha.

**Leitura:**
- **Posição do Sol:** validada.
- **Lado iluminado × lado escuro do relevo, a partir de ~10 m:** validado. A correlação é positiva só com o Sol certo, e todos os controles dão negativo. Ela não passa de ~0,4 porque o brilho da foto é dominado pela cor das camadas de rocha (albedo), não por falha do modelo.
- **Sombra num ponto específico:** fraca. Com o Sol a 32°, o modelo prevê só 0,5% de sombra, e só 11–25% dela cai em pixel escuro da foto (3–5× o acaso). Quase todo o escuro da foto vem de relevo menor que 2 m (cristas, blocos), que o DTM não resolve.
- **Sombra com Sol baixo (manhã e fim de tarde): não validada.** As 35 observações HiRISE do recorte são todas entre 14h e 16h.

## Como usar (e como não usar)

- **Serve para:** orientação de luz em escala de dezenas de metros. Mostra que encosta pega Sol de manhã ou à tarde, quando o morro ou a escarpa projeta sombra longa, de onde vem o ofuscamento e se a luz na volta vai ser rasante.
- **Não serve para:** dizer se um ponto exato está na sombra, nem dar a irradiância nele. Também não serve como critério de segurança.
- O valor em W/m² é o limite superior no topo da atmosfera, sem poeira. Na sombra há luz difusa do céu.
