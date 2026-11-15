# H2G2 · Feature 04 · Status em 13/11/2026 (noite)

Plano completo: `feature04.md`. Este arquivo registra onde paramos e o que se constatou.

## Entregue: tarefas de código 1 a 9

| # | Tarefa | Estado |
|---|---|---|
| 1 | Contrato e mock | pronto (sessão anterior) |
| 2 | Inventário PDS | pronto; `dados/science_index.csv`, 710 linhas |
| 3 | Alvos com posição | pronto; 10 alvos, 3 `exata`, 7 `por_sol` |
| 4 | Medições do chão | pronto; 60 medições reais (APXS, ChemCam, CheMin) |
| 5 | CRISM | pronto com ODE; produto FRT000058A3, ~18 m/px |
| 6 | Terreno | código pronto; espera o `terrain.geojson` da M6 |
| 7 | Endpoint | pronto; três casos ok (alvo perto, longe, fora da janela) |
| 8 | Card na UI | pronto; `web/card.js`, sem `null` nos 5 estados |
| 9 | Pacote offline | ETL da F04 roda sem rede; falta ensaio com o Wi-Fi desligado (manual) |

`science_source: public` agora é o padrão. Mock só com `science_source: mock`.

### Como rodar (a partir de `h2g2-f03/`)

```
../../../.venv/bin/python etl/crism.py               # só se mudar o produto CRISM (baixa ~136 MB para .cache/crism/)
../../../.venv/bin/python etl/build.py --source public
../../../.venv/bin/uvicorn api.main:app --port 8000
../../../.venv/bin/python -m pytest -q               # 7 passed
```

### Arquivos novos

- `etl/sources/science_public.py`: `PublicScience` (alvos, medições, frases por regra fixa) e `PublicOrbital` (CRISM).
- `etl/crism.py`: recorta o SU do CRISM com numpy (sem GDAL) e grava `dados/crism_boxwork.json` (350 KB).
- `web/card.js`: card da ficha. `app.js` chama `/science/card` junto com panorama e fotos.
- `dados/pds/` (400 KB), `dados/mastcam/` (650 KB), `dados/crism_boxwork.json`: tudo o que o ETL precisa offline. O build copia para `bundle/`.

### Regras implementadas

- **Posição:** `exata` quando o nome do alvo aparece num alvo do ChemCam no PDS (Altadena, Valle de la Luna, Nevado Sajama). Senão, vale a parada que o PDS registra no sol de referência (`por_sol`).
- **Mojo:** parada 118_1944 (a do PDS), como decidido. Fica `por_sol`, porque o nome "Mojo" não aparece no PDS. A ficha avisa "posição aproximada pela parada do sol 4643".
- **Medições:** tudo o que foi medido na mesma parada, dentro da faixa de sols da M8. Até 3 APXS, 4 ChemCam (um por alvo do PDS; o de nome igual vem primeiro) e 2 CheMin. Cada linha mostra o nome do alvo no PDS, o sol, o arquivo e a escala ("medido nesta parada" ou "a até ~7 m").
- **Frases:** APXS com os 3 óxidos maiores. Com SO3 ≥ 8%: "enxofre elevado, compatível com sulfatos". Com CaO ≥ 8% e SO3 ≥ 8%: "compatível com sulfato de cálcio". ChemCam: média dos pontos e 3 óxidos maiores (a tabela MOC não mede enxofre); com CaO ≥ 8%: "cálcio alto". CheMin: os 3 minerais maiores da fração cristalina, mais sulfatos, carbonatos, argilas e óxidos de ferro.
- **CRISM:** 5 parâmetros (SINDEX2, BD2100_2, BD1900_2, D2300, BD2210_2) com limiares conservadores escolhidos pela equipe (0,02 / 0,01), que não são valores oficiais. Na janela, nenhum pixel passa do limiar: a ficha diz "sem sinal mineral forte neste pixel" e mostra o maior índice com o valor. É honesto, mas menos vistoso do que "sulfato aqui".
- **Terreno:** ponto-no-polígono em stdlib. Sem `dados/terrain.geojson`, a linha não aparece. Basta salvar o arquivo da M6 e rodar o build.

## Conferência automática feita

- APXS sol 4713 (120_82): SiO2 41,88 · FeO 20,33 · SO3 8,93, iguais ao arquivo bruto.
- CheMin sol 4720: plagioclásio 49,5 · piroxênio 13,6 · anidrita 13,3, iguais ao arquivo bruto.
- ChemCam Nevado_Sajama_cc: média 50,5% de SiO2, coerente com os pontos brutos (51,7 / 48,6 / 51,8...).

## Pendências e avisos

- **Monte Grande e Valle de la Luna** caem na mesma parada (119_1722). O card mostra o de sol menor (Valle de la Luna), então Monte Grande nunca aparece sozinho.
- **Frases da M4:** o card lê as colunas `por_que_importa`, `nota_seguranca` e `fonte_frases` (link) do `m8_alvos.csv`. Enquanto estiverem vazias, a ficha mostra só "o que foi feito" (do blog).
- **F03:** o build avisa `panorama colorido color_PIA26696B: parada 120_82 ou imagem ausente; ignorado`. O PNG do panorama colorido não está no caminho `../dados_panoramas/panos/colored_images.png` depois da mudança de estrutura.
- **Bundle novo sem rede:** as fotos Navcam (F03) dão 0, porque são baixadas direto para o bundle. O bundle atual tem as 211.

## Tarefas manuais restantes

| # | Tarefa | Estado |
|---|---|---|
| M1 | Aba Resources | aberta |
| M2 | Analyst's Notebook (4643, 4693, 4718) | opcional agora: Mojo decidido pelo PDS; serve de conferência |
| M3 | CRISM no ODE | **feita via API**: FRT000058A3, FRT0000B6F1 (~18 m) e HRL0000BABA (~36 m) cobrem a janela |
| M4 | 20 frases com link | aberta; colunas acima |
| M5 | Fotos Mastcam mostram o alvo? | aberta |
| M6 | Polígonos de terreno no QGIS | aberta; salvar em `dados/terrain.geojson` com `classe` e `nota_seguranca` |
| M7 | Perguntas para o Emerson | aberta |
| — | Conferir à mão 3 frases da T4 | aberta |
| — | Ensaio da demo com o Wi-Fi desligado | aberta |

### Roteiro de demo (3 pontos)

1. **Mojo:** parada 118_2028 (lat −4.80679651, lon 137.3794121). Panorama da F03 e ficha do Mojo a ~10 m.
2. **Nevado Sajama:** parada 120_82. 10 linhas: APXS com enxofre elevado, CheMin com anidrita 13,3%, ChemCam no furo.
3. **Ponto sem alvo:** lat −4.8100, lon 137.3770. Só órbita e nome. Vira "mancha de areia" quando a M6 sair.
