# H2G2 · Feature 04 · Status em 13/11/2026

Plano completo: `feature04.md`. Este arquivo registra onde paramos e o que se constatou.

## Entregue (Fase 1 de código: tarefas 1 e 2)

**Tarefa 1: contrato e mock da ficha**
- `etl/sources/base.py`: dataclasses `Target`, `Measurement`, `OrbitalLabel` e Protocols `ScienceSource`, `OrbitalMineralSource`.
- `etl/sources/mock.py`: `MockScience` (10 alvos da M8, 24 medições de exemplo com `confidence="mock"`) e `MockOrbital`.
- `etl/science.py`: grava `targets`, `measurements`, `target_rtree`. `python etl/science.py` refaz só essas tabelas; o `build.py` também chama a etapa.
- `config.yaml`: `science_source: mock`, `card_radius_m: 150`, `science.targets_csv`. As fontes `public` e `official` de ciência levantam `NotImplementedError` até as tarefas 3 a 5.
- `GET /science/card?lat&lon` em `api/main.py`. Linha sem fonte não aparece; aviso "posição aproximada pela parada do sol X"; sem alvo a menos de 150 m devolve "nenhum alvo estudado a menos de 150 m" e só órbita e nome; fora da janela devolve só a mensagem.
- Verificado chamando a função da rota: parada 118_2028 devolve o Mojo a menos de 10 m. Os testes novos em `tests/test_core.py` não rodaram (falta `pytest`).

**Tarefa 2: inventário do PDS**
- `etl/science_index.py` gera `dados/science_index.csv` (710 linhas) e grava a contagem no `inventario_pds` do `MANIFEST.json`. Listas brutas em `.cache/pds/`; `--offline` roda sem internet.

| Instrumento | Linhas |
|---|---|
| APXS | 129 (79 sols) |
| ChemCam LIBS | 216 |
| ChemCam RMI | 362 |
| CheMin | 3 (sols 4566, 4695, 4720) |

## O que constatamos

- APXS cobre os sols 4550–4709 (88 sols antes da Release 42). A dúvida do plano está resolvida.
- O label do APXS não traz o nome do alvo (`TARGET_NAME = MARS`): vínculo só por sol e parada.
- Mojo: o PDS registra o sol 4643 em `118_1944`; a M8 e o `h2g2.db` usam `118_2028`. Decidir qual parada vale antes de gravar `pos_quality="exata"`.
- Altadena (sol 4564) não tem linha no PDS; o CheMin correspondente é o do sol 4566 (`116_1944`).
- Todas as posições de alvo ainda são `por_sol`.

## Próximos passos

1. Manuais em paralelo: M1 (aba Resources), M2 (Analyst's Notebook nos sols 4643, 4693, 4718: resolve a divergência do Mojo), M3 (CRISM no ODE), M4 a M7.
2. Tarefa 3: cruzar `m8_alvos.csv` com `science_index.csv` e gravar `exata` ou `por_sol`.
3. Tarefa 4: ler APXS, ChemCam e CheMin reais; frases por regra fixa; conferir 3 alvos.
4. Tarefa 5: CRISM, limite de 2 h, plano B com Fraeman 2016.
5. Tarefa 6: terreno (`terrain.geojson`, depende da M6).
6. Tarefa 7: endpoint final com dados reais.
7. Tarefa 8: `web/card.js` na UI.
8. Tarefa 9: pacote offline e demo sem Wi-Fi.
