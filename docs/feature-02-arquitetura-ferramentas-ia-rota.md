# Arquitetura: a IA usa o backend como ferramenta pra sugerir rota

14/11/2026 · Ingride · decisão de arquitetura pra fechar o "destaque central"
do projeto (objetivo científico) identificado em
[`plano-real-objetivo-rota-voz.md`](plano-real-objetivo-rota-voz.md), seção 4.

> Este documento substitui a proposta da seção 4 daquele doc ("escolher
> entre os 3 alvos cadastrados") por um mecanismo mais limpo e mais fácil
> de crescer: em vez de lógica fixa de comparação, o backend expõe
> **ferramentas de consulta** que a camada de IA usa pra pegar dado real
> antes de decidir, e quem gera a rota continua sendo o motor que já
> existe. A ideia é da Ingride; este doc só organiza e divide.

## 1. A ideia, em uma frase

A IA (Gemma, com o Hugo) **nunca inventa coordenada nem gera rota
sozinha** — ela entende o objetivo em linguagem natural e **consulta
ferramentas do backend** (meu, feature 02) pra descobrir o que existe de
dado real; o backend então gera a rota de verdade com o motor A* que já
existe, devolve pro frontend os dados completos pra exibição, e devolve
pra IA um resumo estruturado pra ela explicar em voz o que foi sugerido.

## 2. Arquitetura (de ponta a ponta)

```
astronauta fala o objetivo
  └─▶ Whisper transcreve (Hugo)
        └─▶ Gemma interpreta o objetivo (Hugo)
              └─▶ chama a FERRAMENTA "consultar dado local" (minha, backend)
                    └─▶ devolve dado REAL existente (alvos científicos, pontos, medições)
                          -- nunca inventa, só retorna o que já está no banco
              └─▶ Gemma decide o destino (ou diz "nenhum combina", nunca inventa)
                    └─▶ chama a FERRAMENTA "gerar rota" (minha, o /api/route que já existe)
                          └─▶ motor A* + margem de O2 + sugestão (Hugo, Fases 1-4 do plano dele)
                                ├─▶ pro FRONTEND: todas as rotas, com todos os dados já usados
                                │     (alertas por trecho, O2, ida+volta, rótulo ✅/⚠️/⛔, motivo)
                                └─▶ pra IA: resumo estruturado e compacto de cada rota
                                      (pra ela narrar em voz o que foi sugerido)
```

Duas coisas importantes nessa cadeia:

1. **"Ferramenta" aqui pode ser function-calling de verdade do Gemma, ou
   só código Python comum chamando meus endpoints depois que o Gemma
   devolve uma saída estruturada (JSON restrito a uma lista)** — o plano
   de voz do Hugo já usa esse segundo padrão pro nome do destino
   ("Gemma com `format` em JSON schema"). **Isso é decisão técnica do
   Hugo**, porque é a camada de orquestração dele; da minha parte, o que
   importa é que os dois padrões consomem os mesmos endpoints/funções que
   vou expor — não muda o que eu construo, só quem chama.
2. **O motor de rota não muda de dono.** A IA só decide "pra onde"; "como
   chegar lá com segurança" continua sendo inteiramente o
   `route_planning.py` + a sugestão (minha Fase 1-3 + `sugestao_rotas.py`
   do Hugo, já combinado em
   [`plano-real-objetivo-rota-voz.md`](plano-real-objetivo-rota-voz.md)).

## 3. As ferramentas que eu preciso expor

### 3.1 Consulta de dado local por objetivo

```
GET /api/alvos-cientificos
→ [{nome, lat, lon, medicao_curiosity, fonte_url}, ...]  (os alvos já cadastrados, hoje 3)
```

**Decisão técnica recomendada:** esta ferramenta **não filtra nem
pontua nada** — devolve os dados reais crus, e é a IA (Gemma, que já
recebe o objetivo no prompt) quem decide qual combina melhor, ou que
nenhum combina. Com só 3 alvos cadastrados, não compensa construir
busca/ranking no backend — e deixar a decisão na IA é mais simples e
mais fácil de crescer (se amanhã tiver 50 alvos, aí sim valeria pensar
em filtro/busca no backend; hoje seria complexidade sem necessidade).

Esse endpoint é quase todo reaproveitamento: a query já existe em
`vector_queries.todos_alvos_cientificos` (usada por `route_planning.py`
na variante "mais ciência"). É só expor como rota HTTP.

### 3.2 Geração de rota

```
GET /api/route (JÁ EXISTE)
```

Não preciso criar nada novo aqui — é o mesmo endpoint que o clique no
mapa já usa. A única mudança é **quem chama**: hoje é só o clique do
usuário no front; agora também pode ser a camada de orquestração do Hugo,
depois que o Gemma decide o destino. O contrato não muda.

### 3.3 Resumo estruturado pra IA explicar em voz

Isto **já está no plano do Hugo** (`feature-08-voz-plano-execucao.md`,
Fase 3, e `feature-02-sugestao-rotas-plano-execucao.md`, seção sobre
`api/agente.py`): o `contexto_em_texto` ganha um bloco ROTAS com o resumo
de cada rota (rótulo, prós, contras). Ou seja — **a parte "devolver pra
IA entender o que foi sugerido" já tem dono e já tem plano**; não é um
item novo, é confirmar que a ideia dela bate com o que ele já desenhou.

### 3.4 Texto combinando as opções + motivo, pra tela

Isto também **já está no plano do Hugo**: `sugestao_rotas.py` já gera
"frases prontas para tela e voz, cada uma com fonte" (prós/contras) e a
ordem sugerida com o motivo. **Não preciso duplicar essa lógica** — o que
eu preciso garantir é que meus dados (margem de O2, ponto de não retorno,
alertas por trecho com distância, que já fiz) estejam completos e
corretos, porque é em cima deles que o texto dele é gerado. Se eu também
tentasse gerar texto de "motivo da rota" por conta própria, teríamos duas
fontes de verdade pra mesma frase — por isso a recomendação é: **eu
forneço o dado, ele gera o texto.**

## 4. Ferramenta nova do Hugo: análise preditiva de risco da rota

Além de consultar dado pra decidir o destino, a IA também deve avaliar a
rota **já sugerida** contra riscos ambientais previsíveis — não só
inclinação/O2 (que o motor já cobre), mas eventos de ambiente que mudam
com a época/posição. Pedido da Ingride, organizado aqui.

### 4.1 Correção importante sobre os exemplos

Os exemplos originais incluíam "chuva ácida" — **isso não existe em
Marte**: a atmosfera é fina demais (~1% da pressão terrestre) e não há
água líquida estável na superfície, então não chove nada lá, ácido ou
não. Como o projeto inteiro segue "nunca inventar dado" (`CLAUDE.md`),
listar um risco fisicamente impossível quebraria esse princípio mesmo
sendo só um rótulo de severidade. Os riscos reais a pesquisar são outros:

**Verificado contra o projeto real (não suposição) em 14/11/2026:**

| Risco real em Marte | O que realmente existe hoje | Fonte confirmada |
| --- | --- | --- |
| Tempestade de poeira (regional/global, sazonal) | `api/alertas.py` tem `LS_POEIRA = (180°, 360°)`, um intervalo **fixo**, sem probabilidade nenhuma, citado como vindo de "Mars24 / climatologia MCD" | ⚠️ **ALERTA — ver abaixo** |
| Evento de partícula solar / pico de radiação (SPE) | **Não existe nada.** RAD (`data-pipeline/adapters/pds_rad.py`) só dá a dose medida por sol, não prevê picos futuros | Precisaria de dado novo — ex. clima espacial do MAVEN (NASA) — **a procurar do zero**, nunca pesquisado ainda neste projeto |
| Variação extrema de temperatura/pressão | **Parcial.** REMS (`pds_rems.py`, PDS Atmospheres) é a fonte, confirmada e já em uso (F06). Mas só **1 sol está baixado de verdade** (`data/local/conditions/sol_4650.json`). Existe um script (`cache_climatologia.py`) pra amostrar ~3 anos marcianos, mas **nunca rodou** — `climatologia.json` não existe no disco ainda | PDS Atmospheres (REMS) — rodar `cache_climatologia.py` antes de declarar qualquer "probabilidade histórica" |
| Poeira eletrostática / "dust devils" | **Não existe nada.** Só documentado em papers do MSL/InSight, nunca verificado se há dataset público baixável | A procurar do zero — pode não existir em formato usável |

> ⚠️ **ALERTA — fonte não-NASA já em produção, pendência real a resolver**
>
> `LS_POEIRA` cita **MCD (Mars Climate Database)**, que é **francês**
> (LMD/CNRS), **não é da NASA**. Confirmado via `git log -S"LS_POEIRA"`:
> foi inserido pelo **Hugo**, commit `6ec6fb3` ("Adiciona agente local e
> alertas do modo sem Terra — feature 08"), 14/11/2026, junto com o resto
> do módulo de alertas. Ninguém mexeu nisso depois.
>
> **Por que isso importa:** a NASA tem restrição sobre dado vindo de
> determinados países em seus programas e parcerias — não é só a regra
> que o time já tinha fixado pra dado chinês. Isso precisa ser **checado
> contra as regras oficiais do desafio** (aba Resources / termos do NASA
> Space Apps) antes de decidir se o MCD pode continuar sendo citado como
> fonte, mesmo sendo francês. Enquanto isso não for confirmado, **tratar
> como pendência de compliance, não só como "fonte menos precisa"**.
>
> Isso já está em produção hoje (não é um risco só da ferramenta nova
> deste documento) — precisa ir pro time, não é decisão só minha ou só
> do Hugo.

**Regra pro Hugo pesquisar:** só usar fonte NASA/JPL (PDS, Mars Trek,
MAVEN, GISS) ou agências claramente não-chinesas se precisar complementar
(ex. ESA, ou francesa/LMD só se não houver equivalente NASA) — **nunca
dado de origem chinesa** (ex. missão Tianwen-1/Zhurong), por decisão do
time. Se não achar fonte real e verificável pra um risco, ele fica de
fora — mesma regra de "sem dado, sem número" que o resto do projeto já
segue, não uma exceção pra essa ferramenta.

**Importante pro escopo:** de 4 riscos, só 1 (temperatura/pressão) tem
fonte totalmente pronta — e mesmo essa precisa que o `cache_climatologia.py`
rode antes de virar probabilidade de verdade. Os outros 3 exigem pesquisa
de dado nova, não é reaproveitamento. Isso é trabalho real a mais pro
Hugo, não só escrever o módulo — vale ele saber disso antes de estimar
tempo.

### 4.2 O que a ferramenta devolve

```
POST /api/risco-preditivo  (novo, Hugo)
entrada: a rota já calculada (trechos, sol de referência, duração)
saída: [{tipo_risco, probabilidade_pct | categoria, severidade, fonte}, ...]
```

`probabilidade_pct` só aparece se houver dado real pra calcular uma
frequência histórica (ex.: "Ls atual cai na janela de tempestades, que
nos dados históricos ocorrem em X% dos anos marcianos nessa janela").
Sem isso, `categoria` qualitativa ("dentro da temporada de risco",
"fora da temporada") com a fonte — nunca um número inventado só pra
preencher o campo.

### 4.3 O loop que você descreveu, e como evitar que ele vire recursão

A ideia — rota sugerida → análise preditiva → se crítico, devolve pra
sugestão de rotas pra "gerar de novo", com pesos, sem ficar em loop — é
resolvida assim, pra garantir que **nunca haja chamada recursiva**:

- A análise preditiva **não manda recalcular o caminho geométrico** (o
  A* não roda de novo). Ela só devolve um **peso/ajuste de severidade**
  que entra como mais um fator no `sugestao_rotas.py` (que já teria
  entrado em ✅/⚠️/⛔ com base em inclinação e margem de O2).
- `sugestao_rotas.py` reclassifica o rótulo **uma única vez**, somando o
  risco preditivo aos fatores que já tinha (ex.: uma rota que seria ✅ só
  pela inclinação pode virar ⚠️ se cair numa janela de alta chance de
  tempestade de poeira).
- **Não existe uma segunda rodada.** Risco preditivo → ajuste de peso →
  rótulo final. Isso por si só impede o loop, porque não há recursão: a
  análise de risco nunca chama a si mesma nem gera uma rota nova, só
  entra como mais um número na mesma conta que já existia.
- Igual a toda rota no projeto: **nenhuma é escondida**, mesmo que o
  risco preditivo deixe ela ⛔. O astronauta vê todas, com o motivo
  (inclusive o risco ambiental) explicado, e decide.

## 5. O que o backend devolve, resumindo os quatro destinos diferentes

| Devolve pra... | O quê | Quem gera |
| --- | --- | --- |
| **Frontend** (tela) | Todas as rotas com todos os dados (distância, tempo, O2, alertas por trecho, margem, ponto de não retorno, rótulo, prós/contras, ordem sugerida, risco preditivo) | Dados geométricos/O2: eu (`route_planning.py`) · Rótulo/texto/risco preditivo: Hugo (`sugestao_rotas.py` + `api/risco-preditivo`) |
| **IA** (pra narrar em voz) | Resumo compacto por rota (rótulo + 1-2 frases prontas, incluindo risco ambiental se houver) | Mesmo dado de cima, empacotado no bloco ROTAS do `contexto_em_texto` — Hugo |
| **IA** (pra decidir destino) | Lista crua dos alvos científicos reais | Eu — novo endpoint simples, seção 3.1 |
| **`sugestao_rotas.py`** (interno) | Ajuste de peso/severidade vindo da análise preditiva | Hugo — `api/risco-preditivo` alimentando a própria classificação dele, sem segunda rodada |

## 6. Divisão de tarefas (atualizada e final desta etapa)

### Hugo — transcrição, agente de IA, orquestração

- `api/voz.py`: Whisper (transcrição) + `interpretar()` (intenção).
- Orquestração do objetivo científico: receber o texto/fala do objetivo,
  montar o prompt pro Gemma com os dados da ferramenta 3.1, decidir o
  destino (ou "nenhum combina", nunca inventado) e chamar `/api/route`
  com esse destino.
- `api/sugestao_rotas.py`: rótulo ✅/⚠️/⛔, prós/contras, ordem sugerida —
  consome os campos novos que eu vou adicionar em `route_planning.py`.
- `api/agente.py`: bloco ROTAS no `contexto_em_texto`, pra IA conseguir
  explicar em voz o que foi sugerido.
- `web/ui/voz.js` + `voz-captura.js`: captura de áudio, estados.
- **Novo: `api/risco_preditivo.py`** — análise preditiva de risco
  ambiental da rota sugerida (tempestade de poeira, evento de partícula
  solar, variação extrema de temperatura/pressão — ver seção 4 pros
  exemplos corrigidos e as fontes a pesquisar). Alimenta
  `sugestao_rotas.py` como mais um fator de severidade, numa única
  rodada, sem recálculo geométrico — ver seção 4.3 pra não virar loop.
  **Nenhum dado de origem chinesa**, e nenhum risco sem fonte
  real/verificável (mesma regra de "sem dado, sem número" do resto do
  projeto).

### Eu — motor de rota e as ferramentas que ele expõe

- `GET /api/alvos-cientificos`: novo endpoint simples, expõe
  `vector_queries.todos_alvos_cientificos` (reaproveitamento, não lógica
  nova).
- `api/route_planning.py`: Fases 1 (faixa de O2 otimista/pessimista), 2
  (mapa de custo de volta via Dijkstra) e 3 (margem mínima, ponto de não
  retorno, pior trecho de emergência, volta_minutos_max) — já combinado
  em [`plano-real-objetivo-rota-voz.md`](plano-real-objetivo-rota-voz.md).
- `web/ui/rota.js`: exibir todas as rotas (inclusive ⛔), ponto de não
  retorno no mapa, consumindo o rótulo/motivo que o Hugo gera.
- Garantir que `/api/route` aceite ser chamado tanto pelo clique no mapa
  quanto pela orquestração do Hugo — hoje já aceita (é só `origin_lat`,
  `origin_lon`, `dest_lat`, `dest_lon` + paradas opcionais), não preciso
  mudar nada de contrato, só confirmar que funciona chamado de outro lugar
  que não o clique.

### Combinado entre nós dois (fronteira exata da chamada)

- O formato exato do que a ferramenta 3.1 devolve (nomes dos campos) e o
  formato exato do bloco ROTAS que `api/agente.py` espera — preciso
  alinhar o esquema com o Hugo antes de qualquer um dos dois codar, pra
  não ter que ajustar depois.
- Se o Gemma vai chamar minha ferramenta via function-calling de verdade
  ou se o código do Hugo chama meu endpoint depois de uma saída
  estruturada do Gemma — **decisão técnica dele**, não muda meu lado.

## 7. O que fica confirmado, o que ainda é decisão de time

**Confirmado por este documento** (resolve a pergunta em aberto da seção
4 do doc anterior): o objetivo científico entra nesta etapa, e entra como
consulta de ferramenta + decisão da IA restrita a dado real — não como
geração livre de coordenada.

**Ainda em aberto** (herdado do doc anterior, sem mudança):
- Limite de folga de O2 pra ⚠️/⛔ (sem fonte oficial → "proposta H2G2").
- Variante `mais_direta` que permite trecho acima de 20° de propósito.
- Recálculo por obstáculo relatado por voz, pra frente, sem redefinir
  destino — a própria reunião já disse que não é prioridade imediata.
- ⚠️ **Novo, urgente**: `LS_POEIRA` (`api/alertas.py`, já em produção)
  cita o MCD francês como fonte, não a NASA — checar contra as regras
  oficiais do desafio antes de decidir se mantém, documenta a limitação,
  ou troca por fonte NASA equivalente. Ver seção 4.1.

## 8. Ordem de implementação — o que depende de quem

### 8.0 Primeiro passo, antes de qualquer código: alinhar o contrato

Não é tarefa de código, é uma conversa curta (15-30 min) pra travar três
formatos antes de qualquer um de nós dois escrever algo que dependa do
outro:

1. O formato exato de `/api/alvos-cientificos` (seção 3.1).
2. Os nomes dos campos novos de `route_planning.py`: `margem_minima`,
   `ponto_nao_retorno`, `pior_trecho_emergencia`, `volta_minutos_max`
   (seção 3, Fase 3).
3. O formato que `sugestao_rotas.py` e o bloco ROTAS do `agente.py`
   esperam receber (rótulo, prós/contras, risco preditivo).

Sem isso travado, qualquer um de nós pode codar um formato e o outro ter
que reescrever a parte que consome. É o único passo realmente bloqueante
do início — depois dele, muita coisa roda em paralelo.

### 8.1 Pode começar JÁ, em paralelo, sem interferir em nada

| Eu | Hugo |
| --- | --- |
| `route_planning.py` Fase 1 (faixa de O2 otimista/pessimista) — cálculo puro, não depende de ninguém | `api/voz.py` (Whisper + `interpretar()`) — não depende de mim |
| `route_planning.py` Fase 2 (Dijkstra, mapa de custo de volta) — idem | `web/ui/voz.js` + `voz-captura.js` (captura de áudio, estados) — não depende de mim |
| `GET /api/alvos-cientificos` — reaproveitamento simples de `vector_queries.py` | Pesquisa de fonte de dado real pro `risco_preditivo.py` (a pesquisa em si, não a integração — seção 4.1) |

### 8.2 O que tem dependência real (ordem importa)

```
eu: Fase 1 → Fase 2 → Fase 3 (margem/ponto de não retorno)
                                 │
                                 ▼
hugo: sugestao_rotas.py (só fecha de verdade com os campos da minha Fase 3 -- pode escrever o esqueleto antes, mas não testa com dado real sem eles)
                                 │
                                 ▼
hugo: bloco ROTAS no agente.py (depende do sugestao_rotas.py dele mesmo)
                                 │
                                 ▼
eu: web/ui/rota.js, card final com ✅/⚠️/⛔ + motivo (depende do formato que o sugestao_rotas.py do Hugo devolve)

eu: GET /api/alvos-cientificos
                                 │
                                 ▼
hugo: orquestração do objetivo científico (chama meu endpoint -- pode escrever a lógica de prompt antes, mas não roda de ponta a ponta sem ele)

hugo: sugestao_rotas.py (de novo)
                                 │
                                 ▼
hugo: risco_preditivo.py entra como peso (só faz sentido plugar depois que existe o que ele vai pesar)
```

**Resumindo em uma frase:** minhas Fases 1-3 do motor e meu endpoint de
alvos científicos são **pré-requisito** pro trabalho do Hugo fechar de
verdade (ele pode adiantar esqueleto/estrutura, mas não testar
ponta-a-ponta); a voz (transcrição + captura) e a pesquisa de dado pro
risco preditivo **não dependem de mim em nada** e podem rodar 100% em
paralelo desde já.
