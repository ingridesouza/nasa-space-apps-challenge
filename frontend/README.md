# frontend

Núcleo do mapa (feature 01) + planejamento de rota (feature 02) —
React + Vite + TypeScript + MapLibre GL. Direção visual: HUD / centro
de controle de missão (escuro, dados em monoespaçado, acento
vermelho-marte/âmbar/ciano, paleta extraída da landing oficial do
time).

## Rodar

```bash
npm install          # precisa de internet SÓ nesta etapa, uma vez
cp .env.example .env  # ajustar VITE_API_BASE_URL se a API não estiver em :8124
npm run dev
```

Precisa da API rodando (`cd ../api && python -m uvicorn main:app --port 8124`) —
é de lá que vêm os tiles (`/tiles/{layer}/{z}/{x}/{y}.png`), o
sampling de ponto (`/api/point`), a rota (`/api/route`) e as fotos
(`/rover-photos/...`).

## Estrutura

- `src/map/` — MapLibre: `MapCanvas.tsx` (wrapper React, imperativo via
  ref), `style.ts` (monta o style JSON a partir de `layers.ts` +
  calcula `maxBounds`/`minZoom` reais pra não deixar navegar pro vazio
  fora da cobertura), `layers.ts` (config das camadas — espelha
  `data-pipeline/config/layers.yaml`, **atualizar os dois juntos**
  quando uma camada nova for confirmada).
- `src/components/` — painéis do HUD: controle de camadas (com
  miniatura real por camada), condições, briefing de ponto clicado
  (`VerdictBadge` + elevação/slope reais), planejamento de rota
  (`RoutePanel`), fotos (grid + `PhotoLightbox` com navegação).
- `src/api/` — cliente tipado pra toda a API (`client.ts`/`types.ts`).
- `src/theme/tokens.css` — paleta, tipografia e tokens de espaçamento;
  um lugar só pra mudar a cara do app inteiro.

## O que já funciona de verdade (não é mais placeholder)

| Parte | Status |
|---|---|
| Mapa em tiles XYZ reais (CTX/HiRISE/Relevo/THEMIS, zoom/pan contínuo) | ✅ |
| Clique no ponto → elevação/slope reais (DTM, MOLA) + alertas (feature 08) | ✅ |
| Rota A* real (mais segura/mais rápida), veredito + O2 + perfil de elevação | ✅ |
| Fotos próximas + rastro do rover (200 fotos reais, clicáveis) | ✅ |
| Trilha do Curiosity (inclinação medida pelo rover) | ✅, desligada por padrão |
| Toggle/opacidade por camada, com miniatura real | ✅ |
| Mineralogia (CRISM) | fora -- confirmado sem cobertura real no boxwork |

Só os tiles baixados pela amostra real do boxwork existem (bbox
confirmado via MMGIS, ver `../PROXIMOS-PASSOS.md`) -- fora dessa área o
mapa trava o zoom antes de mostrar vazio (`minZoom` calculado pra
cobrir sempre a tela). Isso é esperado, não é bug.

## Offline -- "React é uma preocupação?"

Não, e vale deixar claro por quê (checado linha a linha em
2026-11-14, ver `../PROXIMOS-PASSOS.md` pra lista completa):

- **React/MapLibre/todo o resto do `node_modules` vira bundle estático
  em build** (`npm run build` → `dist/`) e `npm run dev` também só
  serve do que já está instalado localmente -- nenhum dos dois faz
  chamada de rede em tempo de execução. A única dependência de internet
  é o `npm install` em si, que só precisa rodar **uma vez, antes do
  evento**, igual qualquer projeto Node -- não é específico de React.
- **Único ponto externo real que restou**: as fontes (Chakra Petch,
  IBM Plex Sans, JetBrains Mono) são carregadas via CDN do Google em
  `index.html`. Sem internet, isso degrada de forma suave (cai pra
  fonte padrão do sistema) -- não quebra layout nem trava nada, só
  perde a tipografia escolhida. Auto-hospedar os arquivos de fonte
  resolveria isso por completo, se algum dia for prioridade; hoje não
  é crítico o suficiente pra valer o trabalho.
- **O que de fato quebrava sem internet, e já foi corrigido**: as ~200
  fotos do rover apontavam direto pra `mars.nasa.gov` em vez de
  arquivo local (apesar do nome da coluna no banco ser `local_path`).
  Baixadas de verdade agora (`data-pipeline/scripts/download_rover_photos.py`,
  39MB) e servidas pela própria API (`/rover-photos/...`, FastAPI
  `StaticFiles`). Sem isso, toda foto -- grid, lightbox, pins do
  rastro -- viraria ícone de imagem quebrada no evento.
