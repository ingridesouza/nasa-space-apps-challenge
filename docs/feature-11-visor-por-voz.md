# Feature 11 · Visor por voz

O astronauta vê o visor, mas age por voz. Cada bloco da tela tem um id (`m-A`…`m-I`), mostrado pequeno no topo do bloco. Uma frase vira **um** comando padronizado `{alvo, acao, args}`, que o front executa. Nenhum bloco rola: o que não cabe vira página (‹ 1/3 ›).

```
fala ─▶ /api/voz (Whisper, F08) ─▶ rota? (F08) ─▶ comando de interface? ─▶ senão: pergunta ao agente
texto digitado ─▶ /api/comando ───────────────────▶ comando de interface? ─▶ senão: pergunta ao agente
comando ─▶ web/ui/comandos.js valida no catálogo ─▶ handler registrado em app.js
```

## Peças

| Peça | Arquivo |
|---|---|
| Catálogo (fonte única: blocos, nomes falados, ações, argumentos, confirmação) | `web/commands.json` |
| Intérprete: regras, depois Gemma com saída presa a JSON schema | `api/commands.py` · `POST /api/comando` |
| Despachante, selos, foco | `web/ui/comandos.js` |
| Carrossel no lugar da rolagem | `web/ui/paginas.js` |
| Handlers de cada bloco | `web/app.js` (`registrar('m-X', …)`) |

## Blocos

| Id | Fala | Bloco | Ações |
|---|---|---|---|
| m-A | Atlas | Mapa | expandir, recolher, aproximar, afastar, mover, centralizar, ler (elevação na mira) |
| m-B | Vega | Camadas | ligar, desligar, opacidade |
| m-C | Polaris | Rota | planejar, destino_centro*, parada, remover_parada, tipo, sol, ir_sol, o2, medicao*, apagar_medicao*, alvo, próxima, anterior, recolher, expandir, cancelar* |
| m-D | Orion | Panorama | expandir, recolher, girar, aproximar, afastar, centralizar (direção do ponto) |
| m-E | Rigel | Fotos (e barra de imagens) | abrir N, próxima, anterior, recolher, expandir |
| m-F | Altair | Ficha científica | abrir, fechar, próxima, anterior |
| m-G | Draco | Assistente | abrir, fechar, próxima, anterior, ouvir |
| m-H | Castor | Visor | fechar |
| m-I | Pollux | Destino por coordenadas | definir lat/lon* |
| m-J | Antares | Status (avisos) | ler |
| `sis` | Sistema | sem bloco na tela | voltar (Esc), silêncio, microfone (desliga), ajuda |

\* pede "Confirma?" antes, repetindo os valores ouvidos.

Clique no mapa vira **mira**: o centro do mapa. "Atlas, ler", "Polaris, destino aqui" e "Polaris, parada" usam a mira; o astronauta move o mapa por voz ("Atlas, mover norte") até o ponto.

## Decisões

| Decisão | Por quê |
|---|---|
| Na tela, `m-A`; na fala, nome de estrela ("Atlas") | Letra solta em português (bê/dê/ê/pê/tê) o Whisper confunde. Nomes de estrela são palavras comuns em inglês, distintas entre si. Evitados: Sirius ("serious"), Deneb ("denim"), Lyra ("Lara"). O agente se chama **Marvin** ("H2" não serve: o Whisper o escreve de vários jeitos) |
| Regras antes do modelo | Instantâneo e determinístico. O Gemma (dezenas de segundos na CPU) só entra se as regras não entenderem **e** a frase citar bloco ou verbo do catálogo |
| Gemma com `format` = JSON schema (enum de ids e ações) e `validar()` depois | O modelo só escolhe da lista; argumento fora da faixa é barrado |
| Sem bloco citado: blocos abertos → último usado → pergunta "Qual bloco?" | "Próxima" com fotos e ficha abertas é ambíguo: perguntar é melhor que chutar |
| Argumento obrigatório ausente: pergunta | "Liga a camada" → "falta camada. Opções: …". Coordenada nunca é inventada |
| Acerto não fala, só pisca o selo e escreve na linha de estado | Comando de interface frequente com voz a cada um cansa; erro e confirmação falam |

## Ação nova

1. Acrescentar a ação ao bloco em `web/commands.json` (desc, frases faladas, args).
2. Registrar o handler em `web/app.js`. `api/test_comandos.py` falha se faltar handler.

## Fora da voz (de propósito)

| Item | Por quê |
|---|---|
| Religar o microfone | Com o mãos-livres desligado ninguém ouve o pedido: religa segurando espaço ou clicando em "voz" |
| Arrastar o panorama, slider de opacidade | Cobertos por girar e opacidade com valor |
| Campo de texto do assistente | É a entrada alternativa à voz, não um alvo dela |

## Pendente

- Medir com voz real (`make voz-gravar` / `voz-medir`) as frases de comando.
- "Desfazer" último comando.
- Ollama e modelos Whisper precisam estar instalados na máquina da demo.
