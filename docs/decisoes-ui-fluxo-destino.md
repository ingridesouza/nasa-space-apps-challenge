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

---

# Atualização 2026-11-15: fundo do visor, corrida da ficha e limpeza de rótulos

## Visor

- **Fundo padrão = panorama de Marte** (`web/img/mars-pano.jpg`, 4432×1312, servido localmente), escurecido (véu preto 60% + vinheta radial). Antes era preto liso com o texto "Open the panorama (⤢) or a photo to view it here.".
- Texto de visor vazio (`#viewer-empty`) **removido** (HTML, CSS e JS). O fundo já mostra que o visor está livre.
- **Pendência:** a fonte e o crédito da imagem `mars-pano.jpg` não estão registrados. Registrar (instrumento/arquivo) antes da entrega, conforme a diretriz "toda linha exibida carrega fonte". É imagem decorativa, não dado científico.
- `web/img/mars-pov.jpg` (e a cópia solta `imagesmars20160226pathfinder20160226-16.width-1320.jpg` na raiz) não são usados por nada. Não versionados; decidir se entram ou se são apagados.

## Mapa

- Zoom inicial **15 → 14** (visão mais ampla que o HiRISE em resolução máxima).
- `center()` com o mapa no visor usa zoom **14** (antes `max(zoom atual, 16)`); com o mapa expandido continua 16.

## Ficha científica × resposta do agente

- **Corrida corrigida:** uma pergunta feita enquanto um lugar ainda carrega não é mais sobrescrita pela ficha desse lugar. `answersShown` conta as respostas exibidas; `loadPlace` só desenha a ficha se nenhuma resposta chegou desde que começou. Segue a decisão de que o cartão é a **resposta do agente** (ver `feature-08-cartao-resposta.md`).

## Card de rota

- Ícones de veredito (✓/!/✕) removidos dos botões de tipo de rota e do título da sugestão. O veredito continua no `aria-label` e na cor da linha; só o glifo saiu.

## Voz

- Erro de voz aparece **só na tela**, sem fala ("Voice failed. Try again." removido) e sem o sufixo técnico do erro (`e.message.split(' (')[0]`). Motivo: o astronauta não deve ouvir uma falha de reconhecimento no meio da EVA; o texto na tela basta.

## Repositório

- `subprojetos/f03-f04-victoria/` removido. Docs foram para `docs/` (`feature-03-fotos-panorama.md`, `feature-04-ficha-cientifica.md`, `feature-04-status.md`); `coleta.log` apagado (log reproduzível pelo `collect_panoramas.py`). Referências em `CLAUDE.md`, `README.md` e `docs/migracao-front-html-puro.md` atualizadas.
- Nada foi testado em navegador nesta rodada; só leitura do diff.
