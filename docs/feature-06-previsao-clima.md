# Feature 06 · Previsão local do clima (offline)

Status: **implementada** em 14/11/2026 · `api/previsao.py`, `GET /api/previsao?sol=&duracao_min=`, painel de condições, painel da rota, contexto do agente (F08). Cobre os três pedidos da F06 no `H2G2_NasaSpaceApps_DETON8.pdf`.

## O que faz

Estima a temperatura mínima, a temperatura máxima e a pressão de um sol em Gale. O sol padrão é o de hoje, calculado pelo relógio local e pelo Mars24. A estimativa usa só arquivos locais. Toda resposta sai como `confianca: "estimado"`, com uma faixa e o erro medido. Uma estimativa nunca aparece como medição.

## Método

O clima de Marte se repete muito de um ano para o outro na mesma estação. A versão mínima do método citado no plano (de Cabo-García et al. 2019) é:

```
previsto(sol) = climatologia(Ls do sol) + anomalia
anomalia      = observado(sol base) - climatologia(Ls do sol base)
```

- **Climatologia:** média dos sols de **outros** anos com Ls a até ±15°. Os 100 sols mais próximos do sol base ficam de fora. Só entra o que já se sabia no sol base.
- **Anomalia:** o quanto este ano está acima ou abaixo da média. Ela também absorve a subida do rover no Monte Sharp, porque a pressão cai com a altitude.
- **Sem um ano anterior naquela estação:** o campo volta `null`. Nunca é inventado.

## Os três pedidos do PDF

| Pedido | Onde |
|---|---|
| Climatologia por estação (Ls) + correção pelo último sol medido | `prever()` |
| Prever o sol e comparar com o dado real guardado | `previsao_do_sol(sol)` nunca usa o próprio sol como base e devolve `medido` quando o sol está guardado. O painel de condições mostra "teste · sol 4650 previsto a partir do 4640 × medido" |
| Acoplar a previsão à rota e sugerir a melhor janela para a EVA | `janela_eva()`: com `duracao_min` = tempo estimado da rota, monta a curva prevista por hora solar local (climatologia horária + anomalia do sol base) e escolhe a janela cuja hora mais fria é a mais quente. Aparece no painel da rota como "Melhor janela p/ esta EVA" |

## O que mais o modelo prevê (além do clima do ar)

Todas as previsões usam só dado antigo real, guardado no pacote, e saem como "estimado":

| Previsão | Dado de origem | Método | Onde aparece |
|---|---|---|---|
| Temperatura do chão ao meio-dia | REMS, sensor de solo (GTS), canal B | Estação + anomalia. Só leituras de 11h–14h com recalibração boa e sem sombra (marcas do PDS), mediana | Faixa de previsão, agente |
| Radiação do dia | RAD, detector E | **Último sol medido.** O teste mostrou que a estação + anomalia erra mais que isso: quem manda na dose é o ciclo solar de 11 anos, não a estação de Marte. **Não prevê tempestade solar** | Faixa de previsão, dose da EVA na rota, agente |
| Chance de o terreno real passar de 15° | 293 paradas do rover (inclinação medida) × DTM no mesmo lugar | Frequência por faixa de inclinação do mapa. Ex.: mapa 10–15° → o rover mediu ≥15° em 27% (20 de 73) | Painel do ponto, alerta, camada "Risco de inclinação (previsto)", cor dos trechos da rota, agente |

**Regras de segurança da previsão de inclinação:**
- Chance ≥20% com o mapa "seguro" vira **alerta de atenção** e muda o selo do ponto. O alerta aparece em destaque no modo traje.
- Para subir um trecho a **perigo**, a chance tem de ser ≥50% **e** a faixa precisa de pelo menos 20 paradas. A faixa ≥15° tem só 5, então fica em atenção.

## Quando o tempo muda: medição do habitat

O dado novo vem do sensor do habitat ou do traje, não da Terra:
- **Registro:** "＋ medição do habitat", na faixa de previsão, ou `POST /api/medicao`, com mínima, máxima, pressão e, opcionalmente, dose. As faixas físicas são validadas.
- **Base da previsão:** a medição vira o "último sol medido", e a previsão se corrige sozinha, offline. A base aparece como "medição do habitat, sol X".
- **Aviso:** se a medição fugir mais de 3 vezes o erro típico do que o modelo esperava para aquele sol, aparece "fora do normal da estação: a previsão vale menos". É o sinal de que algo mudou (frente fria, poeira).
- **Apagar:** pelo link na própria faixa ou `DELETE /api/medicao/{sol}`.
- **Arquivo:** `data/local/conditions/medicoes_locais.json`, com escrita atômica.

## Na tela

**Faixa "Previsão local"**, embaixo do mapa:
- ‹ sol › e a data na Terra;
- ar, chão, pressão e radiação em destaque;
- curva do dia com a melhor janela de EVA;
- rodapé com o erro típico, a base e o teste previsto × medido.

## Dados

`data-pipeline/scripts/cache_climatologia.py` gera `data/local/conditions/climatologia.json`:

- 1 sol a cada 20, do sol 20 ao 4840. São 231 sols salvos. Outros 12 não têm produto RNV no PDS (buracos no arquivo).
- Cada sol traz só **180 leituras espalhadas**, num único pedido HTTP com vários `Range`: ~120 KB em vez de ~20 MB. O Apache do PDS devolve o arquivo inteiro acima de 200 faixas.
- Cada sol também guarda `temp_por_hora`: a média das leituras por hora solar local (LMST), que alimenta a janela de EVA.
- Por isso, a mínima e a máxima são "das 180 leituras", e não o pico de 1 Hz do `sol_<n>.json`. A previsão usa só essa definição, dos dois lados da conta.
- Cada sol também guarda `solo_meio_dia_c` (REMS, GTS) e `dose_ugy_dia` (RAD, ~9 s por sol de download).
- O script retoma de onde parou. Com internet, leva ~1h30 para os ~240 sols.

## Erro medido (backtest nos próprios dados)

Erro médio absoluto, prevendo sols já medidos, comparado a "repetir o último dado":

| Horizonte | n | T mín. | T máx. | Pressão | Chão 12h | Radiação* | Repetir o último: T mín. / Pressão / Chão |
|---|---|---|---|---|---|
| 20 sols | 201 | 1,9 °C | 3,7 °C | 11,2 Pa | 6,7 °C | 7,5 µGy/dia | 2,0 °C / 17,1 Pa / 6,9 °C |
| 100 sols | 197 | 2,5 °C | 4,3 °C | 13,1 Pa | 9,5 °C | 11,5 µGy/dia | 4,5 °C / 59,0 Pa / 12,0 °C |
| 330 sols | 185 | 3,0 °C | 5,4 °C | 13,1 Pa | 13,4 °C | 23,7 µGy/dia | 8,5 °C / 68,4 Pa / 20,8 °C |

\* A radiação repete o último sol medido. Com estação + anomalia ela errava mais: 9,5 / 17,4 / 32,8 µGy/dia nos três prazos. Dose diária típica em Gale: ~150–250 µGy/dia. O teste usa 165 sols com dado do RAD; os outros não têm arquivo no PDS.

Com a amostra a cada 20 sols, horizontes menores que 20 se comportam como 20. A API devolve o backtest do mesmo horizonte da previsão pedida.

## Limites

- Prevê a média da estação, não o tempo do dia. Não prevê tempestade de poeira. Para poeira, o que existe é o alerta de temporada da F08 (Ls 180°–360°).
- O UV ficou de fora: o sensor degrada com a poeira ao longo da missão, e a série não é comparável entre anos.
- A amostra a cada 20 sols é um atalho. Um sol a cada 5 daria uma climatologia mais lisa, ao custo de 4 vezes o download.

## Natureza da "previsão" de inclinação (leia antes de citar)

O indicador de inclinação **não é uma previsão do terreno**. É uma **frequência histórica de subestimação do DTM**, calibrada nas paradas do rover. O rótulo "(previsto)" da camada e do painel é herança de nome; o que o número diz de fato é: "em terreno que o mapa dá X–Y°, o rover mediu ≥15° em N% das paradas".

| Faixa do mapa | Paradas | ≥15° medido | Chance | IC 95% (aprox.) |
|---|---|---|---|---|
| 0–7° | 110 | 0 | 0% | até ~3% |
| 7–10° | 105 | 1 | 1% | 0,2–5% |
| 10–15° | 73 | 20 | 27% | 18–38% |
| ≥15° | 5 | 4 | 80% | 38–96% |

Valor real: mostra que o DTM de órbita (~5,9 m/px) suaviza as cristas e subestima a inclinação, principalmente na faixa 10–15°. É um achado de calibração, não uma probabilidade de perigo.

**Limites conhecidos:**
- **Viés de seleção (principal):** o rover só para onde é plano e seguro. A tabela descreve onde ele parou, não o terreno. Encostas evitadas ficam sem cobertura, e o erro vai para o lado perigoso (subestima o risco).
- **Medida diferente da do astronauta:** `tilt` é a atitude do corpo do rover (roll e pitch, base de ~3 m, inclui subir em pedra), não a inclinação do chão sob uma bota.
- **Amostra pequena:** a faixa ≥15° tem 5 paradas. "80%" tem IC de 38 a 96%.
- **Paradas não independentes:** vêm em sequência ao longo da trilha, então o IC real é mais largo.
- **Sem validação:** não há holdout nem validação cruzada espacial. Os cortes de 20% e 50% são escolha manual.
- **Zero eventos ≠ risco zero:** "0%" significa menos de ~3%.
- **Duas implementações de inclinação (não verificado):** a tabela usa `_slope_degrees` ([raster_sampling.py](../api/raster_sampling.py)); a camada pinta com `_slope_grid_deg` ([route_planning.py](../api/route_planning.py)). Se diferirem, as faixas não casam com os pixels.

**Como apresentar:** `confianca: "estimado"` (já é o padrão). Citar como "frequência histórica de subestimação do DTM" e mostrar `n` junto do percentual. Nunca como "previsão de perigo" nem como garantia de segurança.

**Pendências (não feitas):** renomear rótulo/tooltip da camada; mostrar `n` e IC no card; validação cruzada deixando trechos inteiros da trilha de fora; conferir numericamente as duas funções de inclinação.
