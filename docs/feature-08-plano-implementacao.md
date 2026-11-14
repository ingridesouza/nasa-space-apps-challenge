# Feature 08 · Plano de implementação

13/11/2026 · Hugo · base: [`feature-08-agente-local.md`](feature-08-agente-local.md)

A fase 1 é detalhada até o nível de arquivo e função, porque é a próxima a ser feita. As fases seguintes ficam no nível de contrato e só serão detalhadas quando a fase 1 estiver pronta.

## Fase 0 · Pré-requisitos (antes de qualquer código novo)

| Item | Situação encontrada | Ação |
| --- | --- | --- |
| Build do frontend | **Quebrado hoje.** `frontend/src/components/PointInfoPanel.tsx:34` usa o tipo `PointResponse` sem importá-lo; `npx tsc -b` falha com 5 erros em cascata. O `npm run dev` funciona porque o Vite não checa tipos. | Acrescentar `PointResponse` ao import de `../api/types`. É uma linha. Avisar a Ingride, porque o arquivo é da feature 01. |
| Posição da base | Não existe no repo, e as regras de volta à base e de zonas sem rádio precisam dela. | Usar provisoriamente a parada do Curiosity no **sol 4650** (`-4.8068928, 137.3798418`), que é o sol de referência da API e o alvo "Cristas de boxwork". Fica numa constante só, para o time trocar depois. |
| Testes | Não há testes automatizados no repo (os `fetch_*_test.py` são scripts de download). | Um arquivo `api/test_alertas.py` com `assert`, rodando com `python` puro, sem pytest. Novo alvo `make test`. |

## Fase 1 · Alertas por regra + memória do terreno + volta à base

Cobre as etapas 1, 7 e 8 do plano. Ao final, clicar em qualquer ponto do mapa mostra os alertas, e a trilha do Curiosity aparece colorida pela inclinação medida.

### 1.1 Contrato: campo novo `alertas` no `/api/point`

É um acréscimo: nenhuma chave existente muda, então a feature 02 (rota) não quebra.

| Chave | Tipo | Exemplo |
| --- | --- | --- |
| `nivel` | `"perigo"` \| `"atencao"` \| `"info"` | `"perigo"` |
| `tipo` | `"inclinacao"` \| `"terreno_historico"` \| `"volta_base"` \| `"sem_dado"` | `"terreno_historico"` |
| `mensagem` | texto pronto para tela e voz | `"O Curiosity mediu 22,4° a 8 m daqui (sol 4309)."` |
| `fonte` | de onde veio o dado | `"MMGIS MSL_waypoints"` |

A lista vem ordenada por gravidade (perigo, atenção, info). Lista vazia quer dizer "nenhum alerta", nunca "seguro".

### 1.2 Backend

**Arquivo novo `api/alertas.py`**, com uma função pública, `alertas_do_ponto(lat, lon, raster_values)`, que devolve a lista acima. Reaproveita o que já existe, sem duplicar limiar:

| Regra | Condição | Nível | Reaproveita |
| --- | --- | --- | --- |
| Inclinação do mapa | `slope_status` do ponto | `perigo` com 20° ou mais, `atencao` com 15° ou mais | `raster_values` que o `/api/point` já calcula |
| Sem dado de inclinação | `slope_deg` é `null` (fora do bbox) | `info`: "sem dado de inclinação aqui" | — |
| Sem dado de areia | `classe_ai4mars` é `null` (sempre, hoje) | `info`: "sem dado de areia" (nunca "sem areia") | — |
| Memória do terreno | parada do rover a até 25 m com `tilt` de 15° ou mais | `classify_slope(tilt)` | `classify_slope` e limites de `api/raster_sampling.py`, `haversine_m` de `api/geo.py` |
| Volta à base | distância até a base acima de 2.000 m | `perigo` | `haversine_m` |

Decisões de implementação:

- **Leitura das paradas:** o arquivo `data/local/rover_waypoints.json` é lido uma vez e guardado em memória (`functools.lru_cache`). São 1.388 paradas; a varredura linear por clique custa milissegundos e não precisa de índice espacial.
- **Arquivo ausente** (se o `make build` não rodou o fetch): a regra de memória do terreno devolve um `info` ("histórico do rover indisponível") e não derruba o endpoint.
- **Várias paradas perto:** só a de maior inclinação vira alerta, para não repetir a mesma mensagem 5 vezes.
- **Constantes no topo do arquivo:** `BASE_LAT_LON`, `RAIO_HISTORICO_M = 25` e `LIMITE_VOLTA_BASE_M = 2000`. São escolhas nossas e o documento de análise já as lista como decisões em aberto.
- **Fica de fora:** a parte de O₂ da regra de volta à base depende do orçamento de O₂ da feature 02 e só entra quando ela existir.

**`api/main.py`:** uma linha a mais em `get_point`, acrescentando `"alertas": alertas_do_ponto(lat, lon, rasters)` à resposta.

**Endpoint novo `GET /api/rover-track`:** devolve as paradas dentro do bbox das camadas (`raster_registry`, a mesma fonte única de bbox que o `/layers` usa), cada uma com `lat`, `lon`, `sol`, `tilt` e `status` (`classify_slope(tilt)`). O frontend não lê `data/local/` direto, por isso o endpoint.

### 1.3 Frontend

| Arquivo | Mudança |
| --- | --- |
| `frontend/src/api/types.ts` | Tipos `Alerta` e `RoverStop`; campo `alertas: Alerta[]` em `PointResponse` |
| `frontend/src/api/client.ts` | `getRoverTrack()`, no mesmo padrão de `getNomenclature()` |
| `frontend/src/map/MapCanvas.tsx` | No `load` do mapa: buscar a trilha e acrescentar uma fonte GeoJSON com duas camadas, uma linha fina ligando as paradas e um círculo por parada colorido pelo `status` |
| `frontend/src/components/PointInfoPanel.tsx` | Lista de alertas no topo do painel, colorida pelo nível, antes dos dados do ponto |

Cores: o MapLibre não lê variáveis CSS, então os círculos usam os valores de `tokens.css`: `#7fe0a8` (seguro), `#f2b33d` (atenção) e `#e8643f` (perigo). O painel usa as próprias variáveis (`--verdict-*`), como já faz com a inclinação.

Fica de fora: liga/desliga da trilha no `LayerControlPanel`. Ele só controla camadas raster; entra quando alguém pedir.

### 1.4 Verificação

**Teste automatizado** (`api/test_alertas.py`, roda com `make test`), usando pontos reais do repo:

| Caso | Ponto | Esperado |
| --- | --- | --- |
| Memória do terreno, perigo | parada do sol 4309 (`-4.78679146, 137.4076395`) | `terreno_historico` em `perigo`, citando 22,4° e o sol 4309 |
| Volta à base | mesma parada: fica a 2.029 m da base provisória | `volta_base` em `perigo` |
| Memória do terreno sem volta à base | parada do sol 4970 (`-4.82096424, 137.3856038`), a 901 m da base | `terreno_historico` com 24,0°, sem `volta_base` |
| Inclinação do mapa | `raster_values` de mentira com 15° e com 20° | `atencao` e `perigo` |
| Fora do bbox | ponto distante, rasters `null` | `info` de "sem dado", sem exceção |
| Arquivo de paradas ausente | caminho apontando para arquivo inexistente | `info` de histórico indisponível, sem exceção |

**Manual:** `curl` no `/api/point` com o ponto do sol 4309; `npx tsc -b` sem erros; no navegador, a trilha aparece e o clique perto do sol 4309 mostra os dois alertas.

### 1.5 Commits

1. Correção do import em `PointInfoPanel.tsx` (separado, porque é da feature 01).
2. `api/alertas.py` + `api/test_alertas.py` + `make test`.
3. Campo `alertas` no `/api/point` + `/api/rover-track`.
4. Frontend: trilha no mapa + alertas no painel.

## Fase 2 · `POST /api/ask` (etapa 2)

- **Entrada:** `{pergunta, lat, lon, sol}`. **Saída:** `{resposta, fontes, alertas}`.
- **Contexto:** o mesmo JSON do `/api/point` (já com `alertas`) mais `/api/conditions` e a feição IAU mais próxima, colado inteiro no prompt.
- **Modelo:** Ollama local (`gemma3:4b`, Google) chamado com `urllib` da biblioteca padrão; sem SDK novo. O Ollama é instalado à parte (`brew install ollama`), fora do `requirements.txt`.
- **Prompt:** responder só com o contexto; citar fonte e sol; dizer "não sei" quando faltar dado; nunca criar nem cancelar um alerta.
- **CORS:** `allow_methods` passa a incluir `POST`.
- **Ollama fora do ar:** responder 503 com mensagem clara; os alertas continuam funcionando, porque não dependem do modelo.
- **Testes:** pergunta fora do contexto responde "não sei"; a resposta sobre o ponto do sol 4309 menciona os 22,4°.
- **Antes de começar:** medir os tokens/s no i5-8600. Se for lento demais, trocar para um modelo de 1,5B.

## Fase 3 · Modo sem Terra (etapa 3)

- Tabela de conjunções (9/jan/2026, 21/mar/2028) e Ls pela fórmula do Mars24, em funções puras, com teste contra datas conhecidas.
- `cache_conditions.py` passa a guardar vários sols e a curva por hora do REMS, não só mínimo e máximo.
- Novas regras em `alertas.py`: idade do dado, temporada de poeira, queda de UV, orçamento de dose e regra dos 25% de Löwe et al.

## Fases seguintes (etapas 4, 5, 6, 9 e 10)

| Etapa | Depende de | Primeiro passo |
| --- | --- | --- |
| 4. Voz | Fase 2 | Caixa de texto no frontend; depois `speechSynthesis`; o microfone com `faster-whisper` por último |
| 5. Corrigir o DTM | — | Baixar em resolução nativa e rodar de novo a comparação com as 25 paradas de 15° ou mais |
| 6. Demo de radiação | Fase 3 | Confirmar o sol de 20/mai/2024 e se ele já está no PDS |
| 9. Zonas sem rádio | Base definida | Linha de visada base–ponto sobre o DTM, com teste num ponto atrás de relevo conhecido |
| 10. Mapa geológico do USGS | — | Descobrir o serviço ArcGIS das unidades geológicas para o bbox (mesma técnica usada na nomenclatura) |

## Riscos

- **A base provisória decide o alerta de volta à base.** Se o time escolher outra posição, os casos de teste de distância mudam. É uma constante só.
- **A parada do rover não é o ponto exato da inclinação.** O erro de localização do MMGIS é de alguns metros, e por isso o raio de 25 m.
- **A trilha dentro do bbox tem 293 paradas.** É leve para o MapLibre, mas se passar a usar a missão inteira (1.388), vale filtrar pelo bbox, como o endpoint já faz.
