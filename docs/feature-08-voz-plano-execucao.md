# Feature 08 · Plano de execução da voz

14/11/2026 · Hugo · base: [`feature-08-agente-local.md`](feature-08-agente-local.md) (etapa 4) e [`feature-08-plano-implementacao.md`](feature-08-plano-implementacao.md)

## Objetivo

O astronauta não digita. Ele diz **"Guia, qual a melhor rota até a base?"**. O sistema percebe a fala sozinho, transcreve, entende o pedido, confirma em voz alta, calcula a rota, desenha no mapa e fala o resumo. Tudo offline, no mesmo notebook.

```
microfone ─▶ detector de fala (navegador) ─▶ Whisper (API) ─▶ palavra "Guia"?
   ─▶ intenção: regras → Gemma só se as regras não entenderem
   ─▶ "Entendi: rota até a base. Confirma?" ─▶ "sim"
   ─▶ /api/route (já existe) ─▶ mapa desenha ─▶ fala o resumo (texto montado por regra)
```

## Decisões (e por quê)

| Decisão | Escolha | Por quê |
| --- | --- | --- |
| Modelo de transcrição | `large-v3` se a fase 0 medir até ~5 s por frase; senão `turbo` | O `large-v3` é o Whisper mais preciso fora do inglês. O `turbo` tem só 4 camadas no decodificador e perde precisão nisso |
| Idioma | Detectado, mas **só entre os permitidos** (`pt`, `en`) | A detecção livre erra em frase curta e transcreve português "em inglês" |
| "Treino" para hoje | Lista de palavras do domínio e nomes de destinos passados ao Whisper | Fine-tuning precisa de horas de áudio rotulado e de GPU. Fica para depois, com o áudio gravado em uso real |
| Como o áudio chega à API | O navegador já manda o áudio bruto em 16 kHz | Evita a biblioteca de decodificação de áudio do Python, hoje incompatível com o faster-whisper neste ambiente |
| Ativação | Palavra **"Guia"** no início da frase, mais "segure espaço para falar" como plano B | Uma palavra comum em português o Whisper transcreve bem. "H2G2" ele escreveria de dez jeitos |
| Quem decide a intenção | Regras de palavras-chave primeiro, e o Gemma (com saída presa a uma lista) só se as regras não entenderem | As regras respondem na hora e não erram nos comandos principais. O Gemma escolhe só de uma lista fixa e **nunca inventa coordenada** |
| Confirmação | Obrigatória para ação (rota). Para pergunta, a resposta começa com "Você perguntou: …" | Uma palavra mal ouvida não pode virar rota errada |
| Resumo falado da rota | Montado por regra a partir da resposta do `/api/route` | Número vem do dado, nunca do modelo |

**Destinos aceitos por voz:** base, ponto marcado no mapa e os 3 alvos científicos do banco (Cristas de boxwork, Altadena, Totoral/Sillar). A lista é lida do banco, sem nome inventado. Um destino fora da lista recebe a resposta "não conheço esse lugar" e a lista é falada.

## Fase 0 · Pré-requisitos (30 min)

| Item | Ação |
| --- | --- |
| Modelo `large-v3` | Baixar no build para `data/local/whisper/`, como já foi feito com o `small` e o `turbo` |
| Frases de teste | Gravar 10 frases reais no notebook da demo (`data/local/voz_teste/*.wav` + `esperado.txt`): "Guia, qual a melhor rota até a base", "Guia, rota até Altadena", "Guia, posso subir aqui com segurança", "sim", "não", etc. |
| Medição | Script de medição: tempo e taxa de erro por modelo (`large-v3` × `turbo`), com distância de edição pela biblioteca padrão. **Escolher o modelo pelo resultado** e gravar a escolha em `H2G2_WHISPER` |

## Fase 1 · Ouvir: transcrição (1h30)

**API, `api/voz.py`**
- `transcrever(audio_16k)` devolve `{texto, idioma, confianca}`.
- O modelo é carregado uma vez e fica em memória.
- `language` é escolhido por `detect_language` só entre `pt` e `en`.
- O Whisper recebe a lista de palavras do domínio com os nomes dos destinos, além de corte de silêncio, `beam_size=5` e `condition_on_previous_text=False`.
- Trecho com muita chance de silêncio ou baixa confiança volta como `texto: null` ("não entendi"), nunca como frase inventada.

**API, `POST /api/voz/transcrever`**
- O corpo é o áudio bruto (float32, 16 kHz, mono).
- Limite de 15 s, cerca de 1 MB. Acima disso, responde 413.

**Front, `web/ui/voz.js` + `web/ui/voz-captura.js` (AudioWorklet)**
- Microfone com cancelamento de eco, supressão de ruído e ganho automático.
- `AudioContext` em 16 kHz.
- Estado sempre visível: ouvindo / transcrevendo / pensando / falando.

## Fase 2 · Entender e confirmar (1h30)

**API, `interpretar(texto)` em `api/voz.py`**
1. Verificar a palavra de ativação "Guia" no começo da frase, com comparação aproximada ("guia", "gia", "a guia").
2. Aplicar as regras: rota, caminho, ir, levar e "até" viram `rota`; voltar e base viram `rota` até a base; sim, confirmo e pode viram `sim`; não e cancela viram `nao`; o resto vira `pergunta`.
3. Se for rota e as regras não acharem o destino, chamar o Gemma com `format` em JSON schema e `destino` restrito à lista. O Gemma também pode responder "nenhum".

**API, `POST /api/voz/comando` com `{texto, ponto?}`**
- Devolve `{intencao, destino: {nome, lat, lon} | null, fala}`.
- `fala` é a frase de confirmação.

**Front**
- Depois de "Entendi: rota até Altadena. Confirma?", escutar por 8 s **sem exigir a palavra de ativação**.
- "Sim" segue para a fase 3. "Não" ou silêncio cancela, e o sistema fala "cancelado".

## Fase 3 · Agir e mostrar (1h)

- **Rota:** chamar a função de rota que já existe no front, com origem no ponto marcado ou na base e com o destino resolvido. O mapa desenha como hoje.
- **Fala da rota:** o primeiro alerta de **perigo** é falado antes de tudo. Depois vem "Rota mais segura: 1,2 km, cerca de 25 minutos, inclinação máxima 14°", com todos os números lidos do `/api/route`.
- **Pergunta:** vai para o `/api/ask` que já existe. O perigo é falado na hora, e depois "Você perguntou: …" e a resposta do Gemma.
- **Enquanto o sistema fala, o microfone fica mudo**, para o sistema não ouvir a si mesmo.

## Fase 4 · Mãos-livres (1h30)

- **Detector de fala no AudioWorklet, por energia, sem biblioteca:**
  - o limiar se adapta ao ruído de fundo medido nos primeiros 2 s;
  - a gravação começa depois de 150 ms acima do limiar e guarda os 300 ms anteriores;
  - termina depois de 800 ms de silêncio, com no máximo 15 s.
- A frase segue para a fase 1. Sem a palavra "Guia", é ignorada sem aviso.
- Um interruptor "mãos-livres" liga e desliga esse modo. O "segure espaço" continua valendo.

Ordem de entrega: **1 → 2 → 3 com "segure espaço"** já fecha o ciclo inteiro e garante a demo. A fase 4 vem por cima.

## Fase 5 · Depois de hoje

- Voz de saída melhor com Kokoro (pt-BR, licença Apache, roda sobre o ONNX Runtime já instalado).
- Gravar cada comando real com o texto corrigido e, com algumas horas de áudio, fazer fine-tuning (LoRA) do modelo escolhido.
- Mais destinos por voz: paradas do Curiosity por sol ("parada do sol 4309").

## Testes

- `api/test_voz.py` (com `assert`, como os outros):
  - `interpretar` com "Guia, qual a melhor rota até a base" deve dar rota até a base;
  - "rota até Altadena" deve dar o alvo correto;
  - "sim", "confirmo" e "não" devem ser reconhecidos;
  - frase sem "Guia" deve ser ignorada;
  - destino desconhecido deve dar `destino: null`;
  - baixa confiança deve dar `texto: null`.
- O script da fase 0 roda de novo antes da demo e compara o resultado com a medição do início.
- **Aceitação:** com o Wi-Fi desligado, dizer "Guia, rota até Altadena", depois "sim", e ver a rota desenhada e ouvir o resumo.

## Riscos

| Risco | Plano B |
| --- | --- |
| Latência somada (Whisper + Gemma) passa de 10 s | Os comandos de rota vão só pelas regras, sem o Gemma. Se ainda assim estiver lento, usar o `turbo` |
| Sala do pitch barulhenta | Desligar o mãos-livres e usar "segure espaço" com headset |
| Whisper inventa frase no silêncio | Corte de silêncio, mais a rejeição por baixa confiança, mais a exigência de "Guia" |
| Microfone não liberado (o navegador exige `localhost` ou HTTPS) | Abrir sempre por `http://localhost:8000` |
