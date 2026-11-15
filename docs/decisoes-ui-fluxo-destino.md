# Decisões de UI: fluxo do destino e barra lateral (2026-11-14)

Registro das decisões tomadas com a usuária ao revisar o front (`web/`). Código em `web/app.js`, `web/map.js`, `web/ui/rota.js`, `web/ui/camadas.js`, `web/style.css`.

## Fluxo

- **Não há destino padrão.** `estado.destino` começa `null`. O centro `[137.384, -4.801]` em `map.js` é só câmera.
- **Barra lateral fechada e travada** ao abrir o sistema (sem botão de recolher, nada carregado para a posição atual).
- **Destino escolhido e rota calculada → a barra abre** com panorama, fotos e ficha científica **do destino**, não da origem. Antes, os dados eram da posição atual e só trocavam ao minimizar o mapa.
- Mudar paradas ou tipo de rota não recarrega a barra (mesmo destino). Rota com erro: a barra não abre.
- Cancelar a rota fecha e trava a barra de novo.
- Com o mapa aberto, os cards do destino aparecem por cima do mapa.
- O card de rota só aparece depois de haver destino (a instrução no topo guia o clique).

## Marcadores do mapa

| Marcador | Visual |
|---|---|
| Posição atual (início do trajeto) | bola cinza escura, borda clara |
| Destino | bandeira de chegada laranja; a base do mastro marca o ponto exato |
| Parada do panorama | bola pequena cinza clara, opaca, sem brilho |
| Parada intermediária da rota | bola cinza clara (12 px) |

O ícone "i" que vazava sobre o mapa era o hotspot do Pannellum (visibility inline); escondido com a barra recolhida.

## Card de rota

- Topo: legenda **Inclinação** (verde `< 15°`, âmbar `15–20°`, laranja `≥ 20°`) com o botão **+ parada no caminho** à direita.
- Origem, paradas, Destino, **Comprimento da rota** (só ida) e **Tempo · ida + volta** ficam no mesmo bloco.
- Removidos: janela da EVA / clima / Ar / Pressão / medição do habitat, perfil de elevação, dose RAD, lista de alertas "O Curiosity mediu…", modal "Rota · sem destino".
- Card de status (Destino / Perto de / Distância da parada) removido; nomenclatura IAU/USGS não é mais carregada.
- Título "Camadas" removido do seletor de camadas; spinner dos campos LAT/LON removido.

## Pendências e observações

- A cor da linha usa o status **previsto** (`status_previsto`), que pode subir um trecho acima do que a inclinação em graus da legenda indica.
- Alertas do Curiosity (parada medida com 17,5° no sol 4634) vêm do rover, não do relevo de órbita. Ideia descartada por ora: pino na parada medida (exigiria devolver lat/lon da parada em `/api/route`).
- A ficha científica é buscada no destino (raio 150 m) e ignora a parada do panorama.
- Código morto em `web/ui/rota.js`: `secaoEva`, `formMedicao`, `perfilSvg` e seus handlers; variável `ultimo` em `app.js`. Remover quando confirmado.
- Nada foi testado em navegador; só `node --check` nos módulos.
