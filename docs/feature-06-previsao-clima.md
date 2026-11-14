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

## Dados

`data-pipeline/scripts/cache_climatologia.py` gera `data/local/conditions/climatologia.json`:

- 1 sol a cada 20, do sol 20 ao 4840. São 231 sols salvos. Outros 12 não têm produto RNV no PDS (buracos no arquivo).
- Cada sol traz só **180 leituras espalhadas**, num único pedido HTTP com vários `Range`: ~120 KB em vez de ~20 MB. O Apache do PDS devolve o arquivo inteiro acima de 200 faixas.
- Cada sol também guarda `temp_por_hora`: a média das leituras por hora solar local (LMST), que alimenta a janela de EVA.
- Por isso, a mínima e a máxima são "das 180 leituras", e não o pico de 1 Hz do `sol_<n>.json`. A previsão usa só essa definição, dos dois lados da conta.
- O script retoma de onde parou. Com internet, leva ~40 min.

## Erro medido (backtest nos próprios dados)

Erro médio absoluto, prevendo sols já medidos, comparado a "repetir o último dado":

| Horizonte | n | T mín. | T máx. | Pressão | Repetir o último: T mín. / Pressão |
|---|---|---|---|---|---|
| 20 sols | 201 | 1,9 °C | 3,7 °C | 11,2 Pa | 2,0 °C / 17,1 Pa |
| 100 sols | 197 | 2,5 °C | 4,3 °C | 13,1 Pa | 4,5 °C / 59,0 Pa |
| 330 sols | 185 | 3,0 °C | 5,4 °C | 13,1 Pa | 8,5 °C / 68,4 Pa |

Com a amostra a cada 20 sols, horizontes menores que 20 se comportam como 20. A API devolve o backtest do mesmo horizonte da previsão pedida.

## Limites

- Prevê a média da estação, não o tempo do dia. Não prevê tempestade de poeira. Para poeira, o que existe é o alerta de temporada da F08 (Ls 180°–360°).
- O UV ficou de fora: o sensor degrada com a poeira ao longo da missão, e a série não é comparável entre anos.
- A amostra a cada 20 sols é um atalho. Um sol a cada 5 daria uma climatologia mais lisa, ao custo de 4 vezes o download.
