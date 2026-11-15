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
| Catálogo (fonte única: blocos, nomes falados, ações, argumentos, confirmação) | `web/comandos.json` |
| Intérprete: regras, depois Gemma com saída presa a JSON schema | `api/comandos.py` · `POST /api/comando` |
| Despachante, selos, foco | `web/ui/comandos.js` |
| Carrossel no lugar da rolagem | `web/ui/paginas.js` |
| Handlers de cada bloco | `web/app.js` (`registrar('m-X', …)`) |

## Blocos

| Id | Fala | Bloco | Ações |
|---|---|---|---|
| m-A | Alfa | Mapa | expandir, recolher, aproximar, afastar, mover, centralizar |
| m-B | Bravo | Camadas | ligar, desligar, opacidade |
| m-C | Charlie | Rota | planejar, tipo, sol, alvo, próxima, anterior, recolher, expandir, cancelar* |
| m-D | Delta | Panorama | expandir, recolher, girar, aproximar, afastar |
| m-E | Eco | Fotos | abrir N, próxima, anterior |
| m-F | Foxtrot | Ficha científica | abrir, fechar, próxima, anterior |
| m-G | Golf | Assistente | abrir, fechar, próxima, anterior |
| m-H | Hotel | Visor | fechar |
| m-I | Índia | Destino por coordenadas | definir lat/lon* |

\* pede "Confirma?" antes.

## Decisões

| Decisão | Por quê |
|---|---|
| Na tela, `m-A`; na fala, alfabeto fonético ("Alfa") | Letra solta em português (bê/dê/ê/pê/tê) o Whisper confunde. É o padrão de rádio em EVA |
| Regras antes do modelo | Instantâneo e determinístico. O Gemma (dezenas de segundos na CPU) só entra se as regras não entenderem **e** a frase citar bloco ou verbo do catálogo |
| Gemma com `format` = JSON schema (enum de ids e ações) e `validar()` depois | O modelo só escolhe da lista; argumento fora da faixa é barrado |
| Sem bloco citado: blocos abertos → último usado → pergunta "Qual bloco?" | "Próxima" com fotos e ficha abertas é ambíguo: perguntar é melhor que chutar |
| Argumento obrigatório ausente: pergunta | "Liga a camada" → "falta camada. Opções: …". Coordenada nunca é inventada |
| Acerto não fala, só pisca o selo e escreve na linha de estado | Comando de interface frequente com voz a cada um cansa; erro e confirmação falam |

## Ação nova

1. Acrescentar a ação ao bloco em `web/comandos.json` (desc, frases faladas, args).
2. Registrar o handler em `web/app.js`. `api/test_comandos.py` falha se faltar handler.

## Pendente

- Medir com voz real (`make voz-gravar` / `voz-medir`) as frases de comando.
- "Desfazer" último comando.
- Ollama e modelos Whisper precisam estar instalados na máquina da demo.
