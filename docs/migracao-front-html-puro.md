# Migração do front: React/Vite → HTML + CSS + JS puro

Status: **fases 0–4 implementadas em `web/`** (2026-11-14); fase 5 (remover `frontend/`) feita em 2026-11-14 · Escopo: features 01, 02 e 08 no navegador (o que hoje está em `frontend/`)

## 1. Por quê

O `CLAUDE.md` exige front em HTML/CSS/JS puro e funcionamento 100% offline. O `frontend/` atual quebra as duas regras:

| Problema | Onde |
|---|---|
| React 19 + TypeScript + Vite, precisa de `npm install` e de um build | `frontend/package.json` |
| Fontes carregadas do Google Fonts (fica sem fontes quando está offline) | `frontend/index.html` |
| API em outra origem (`http://localhost:8000` via `.env`), o que exige CORS e duas portas | `frontend/src/api/client.ts:11`, `api/main.py` (CORSMiddleware) |

## 2. Resultado esperado

- A pasta `web/` na raiz é servida pela própria API em `http://localhost:8000/`.
- Basta `make run` para subir tudo. Não tem Node nem `npm`, nem `.env` de front.
- Todas as bibliotecas e fontes ficam no repo (`web/lib/`, `web/fonts/`).
- O comportamento é o mesmo do React atual: mesmas telas, mesmos endpoints, mesmo visual.

## 3. Estrutura alvo

```
web/
  index.html            # esqueleto estático (HUD, colunas, botão de rota, overlays)
  style.css             # tokens.css + index.css + @font-face locais
  app.js                # estado + orquestração (substitui App.tsx)
  api.js                # fetch da API (substitui api/client.ts)
  map.js                # MapLibre: estilo, camadas, marcadores, rota, fotos, trilha
  layers.js             # TOGGLEABLE_LAYERS / PLANNED_LAYERS / LAYER_MAXZOOM / cores de veredito
  ui/
    paineis.js          # TopHud + LayerControlPanel + ConditionsPanel
    ponto.js            # PointInfoPanel + NearbyPhotosSection + ScienceTargetSection + VerdictBadge
    rota.js             # RoutePanel + perfil de elevação (SVG)
    lightbox.js         # PhotoLightbox
    util.js             # esc(), num(), veredito (VerdictBadge), feição mais próxima
  lib/maplibre/         # 6.17.0 (hash conferido com o package-lock): .mjs + worker .mjs + .css + LICENSE
  fonts/                # copiadas do antigo front do F03/F04 (já removido)
```

**Biblioteca vendorizada: só o MapLibre GL.** Justificativa: renderiza os tiles raster locais, as camadas GeoJSON (rota, fotos, trilha) e os controles de zoom. Reescrever isso não compensa. O Leaflet do subprojeto F03 não substitui o MapLibre, porque o `map.js` usa `setPaintProperty`, camadas `circle`/`line` e `maxzoom` por camada.

## 4. Mapeamento arquivo a arquivo

| React (hoje) | Linhas | Vira | Como |
|---|---|---|---|
| `main.tsx`, `index.html` | 10 | `web/index.html` | `<script type="module" src="app.js">` e os containers fixos no HTML |
| `api/client.ts` | 85 | `api.js` | Tirar os tipos. `API_BASE_URL = ''` (mesma origem) |
| `api/types.ts` | 174 | — | Sai. Se precisar, vira JSDoc `@typedef` em `api.js` |
| `map/layers.ts` | 57 | `layers.js` | Tirar as interfaces |
| `map/style.ts` | 141 | `map.js` | Tirar os tipos. A lógica (`dataBounds`, `minZoomToCover`, `buildStyle`) fica igual |
| `map/nomenclature.ts` | 36 | `ui/ponto.js` | Função pura, só tirar os tipos |
| `map/MapCanvas.tsx` | 382 | `map.js` | Cada `useEffect([x])` vira uma função exportada (`setPickMode`, `setRoute`, `setPhotos`, `setPhotosVisible`, `setRoverTrackVisible`, `setOrigem`, `setDestino`). Os `useRef` viram variáveis do módulo |
| `App.tsx` | 247 | `app.js` | Os `useState` viram um objeto `estado`. Cada handler muda `estado` e chama o render do painel afetado |
| `theme/verdict.ts` | 21 | `ui/util.js` | Copiar |
| `theme/tokens.css`, `index.css` | 456 | `style.css` | Copiar. Os `style={{…}}` inline do JSX viram classes |
| `components/TopHud.tsx` | 68 | `ui/hud.js` | `renderHud(el, {ponto, sol, zoom})` |
| `components/LayerControlPanel.tsx` | 212 | `ui/camadas.js` | Os checkboxes e sliders chamam `map.setLayoutProperty` / `setPaintProperty` direto |
| `components/ConditionsPanel.tsx` | 69 | `ui/condicoes.js` | Render único, depois do `getConditions()` |
| `components/PointInfoPanel.tsx` + `NearbyPhotosSection` + `ScienceTargetSection` + `VerdictBadge` | 346 | `ui/ponto.js` | `abrirPonto(lat, lon)` faz o fetch e renderiza os estados carregando / erro / dados |
| `components/RoutePanel.tsx` | 291 | `ui/rota.js` | Abas por `tipo`, estatísticas, avisos e `ElevationProfile` (já é SVG inline, vira template string) |
| `components/PhotoLightbox.tsx` | 134 | `ui/lightbox.js` | Overlay com teclas ← → Esc via `keydown` |

### Padrão de componente

```js
// ui/condicoes.js
import { esc } from './util.js'
export function renderCondicoes(el, { conditions, error }) {
  if (error) { el.innerHTML = `<p class="h2g2-erro">${esc(error)}</p>`; return }
  if (!conditions) { el.innerHTML = '<p class="h2g2-dim">carregando…</p>'; return }
  el.innerHTML = `…${esc(conditions.sol)}…`
}
```

Regras:
- **Todo texto vindo da API passa por `esc()`** antes de entrar em `innerHTML`.
- Para eventos, usar `addEventListener` no container, delegando com `e.target.closest('[data-acao]')`. Assim nada se perde quando o HTML é refeito.
- Nada de reatividade genérica nem "mini-framework". Cada handler chama explicitamente os renders que mudaram.

## 5. Mudanças fora do `web/`

1. **`api/main.py`**, no **fim do arquivo**, depois de todas as rotas:
   ```python
   WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "web")
   app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
   ```
   O mount em `/` tem que vir por último, senão ele engole `/api/*`, `/tiles/*` e `/layers`.
2. **CORS:** o `CORSMiddleware` pode sair quando o `frontend/` for removido, porque tudo passa a ser mesma origem.
3. **`Makefile`:** tirar `cd frontend && npm install …` do `build`. O alvo `front` sai, ou passa a só imprimir "abra http://localhost:8000".
4. **`README.md`:** trocar a seção "API + frontend React" (linhas ~20–33, 71, 90–103).
5. **Vendorização do MapLibre** (passo único de desenvolvedor, nunca em runtime): baixar `maplibre-gl.js` e `.css` da mesma versão do `package.json` para `web/lib/` e commitar. Anotar a versão num comentário no topo do `index.html`.

## 6. Ordem de execução

Cada fase termina com o app abrindo e funcionando. Dá para commitar fase a fase.

| Fase | Entrega | Critério de pronto |
|---|---|---|
| 0 | `web/` + MapLibre/fontes vendorizados + mount na API | `localhost:8000` abre o mapa com CTX/HiRISE, `maxBounds` e `minZoom` iguais ao React |
| 1 | Camadas + condições + HUD | Liga/desliga e opacidade de cada camada; painel REMS/RAD; sol e zoom no HUD |
| 2 | Clique no ponto | Painel do ponto com fotos próximas, alvo científico, alertas, nomenclatura |
| 3 | Fotos do rover + lightbox + trilha | Pins clicáveis, lightbox navegável, trilha do Curiosity desligada por padrão |
| 4 | Rota | Modo rota (passo 1/2 e 2/2, cursor de mira), marcadores, linha no mapa, abas mais segura / mais ciência…, radiação, perfil de elevação, avisos |
| 5 | Limpeza | Apagar `frontend/`, CORS, alvo `front` do Makefile, atualizar README |

Estimativa: 1–2 dias para uma pessoa. As fases 0 e 4 são as maiores.

## 7. Teste de aceitação

1. `make build` (com internet, só ETL) e depois **desligar o Wi-Fi**.
2. `make run` e abrir `http://localhost:8000`.
3. Na aba Network do DevTools: **zero requisições para fora de `localhost`**.
4. Percorrer o roteiro: alternar camadas → clicar num ponto → abrir uma foto → planejar rota nos 3 tipos → ver avisos e perfil.
5. Comparar lado a lado com o React (antes de apagá-lo). Precisa ter as mesmas informações na tela.
6. `grep -rn "http" web/ --include=*.js --include=*.html --include=*.css` → nenhuma URL externa (fora `lib/`, conferir manualmente).

## 8. Riscos e decisões em aberto

- **Fontes:** o subprojeto só tem Chakra Petch 400/500/600. O React pede 700 também. Usar 600 no lugar ou baixar o 700 no build.
- **Dois fronts puros:** o antigo front do F03/F04 (Leaflet + Pannellum, já removido de `subprojetos/`) continua separado. A fusão dos dois é outra tarefa. Este plano só evita divergência de estilo, reaproveitando as mesmas fontes e tokens.
- **Sem TypeScript:** perde-se a checagem do contrato `/api/point`. Isso é mitigado pela regra do `CLAUDE.md` de só acrescentar chaves, e pelo teste manual da fase 2.
- **Paridade visual:** os `style={{…}}` inline espalhados pelos `.tsx` precisam virar classes com cuidado. É o ponto com mais chance de regressão visual.
