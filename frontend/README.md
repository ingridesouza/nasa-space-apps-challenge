# frontend

Núcleo do mapa da feature 01 — React + Vite + TypeScript + MapLibre GL.
Direção visual: HUD / centro de controle de missão (escuro, dados em
monoespaçado, acento âmbar/ciano).

## Rodar

```bash
npm install
cp .env.example .env     # ajustar VITE_API_BASE_URL se a API não estiver em :8000
npm run dev
```

Precisa da API rodando (`cd ../api && python -m uvicorn main:app --reload`) —
é de lá que vêm os tiles (`/tiles/{layer}/{z}/{x}/{y}.png`) e o
sampling de ponto (`/api/point`).

## Estrutura

- `src/map/` — MapLibre: `MapCanvas.tsx` (wrapper React), `style.ts`
  (monta o style JSON a partir de `layers.ts`), `layers.ts` (config das
  camadas — espelha `data-pipeline/config/layers.yaml`, **atualizar os
  dois juntos** quando uma camada nova for confirmada).
- `src/components/` — painéis do HUD: controle de camadas, painel do
  ponto clicado (elevação/slope reais + seções placeholder de fotos e
  ficha científica, prontas pro Hugo/Victoria preencherem).
- `src/api/` — cliente tipado pro `/api/point`.
- `src/theme/tokens.css` — paleta e tipografia.

## O que já funciona de verdade vs. placeholder

| Parte | Status |
|---|---|
| Mapa com tiles reais (CTX/HiRISE, zoom contínuo) | ✅ |
| Clique no ponto → elevação/slope reais (DTM, MOLA) | ✅ |
| Toggle/opacidade de camada (THEMIS) | ✅ |
| Fotos próximas / ficha científica | lógica pronta, dado vazio (ver `../PROXIMOS-PASSOS.md`) |
| Relevo (hillshade) / mineralogia no mapa | desabilitado — sem pirâmide de tiles visual ainda |
| Hora/sol marciano no HUD superior | placeholder estático |

Só os tiles baixados pela amostra de teste (bbox `~137.40-137.48,
-4.61~-4.57`) existem — fora dessa área o mapa fica em branco. Isso é
esperado, não é bug.
