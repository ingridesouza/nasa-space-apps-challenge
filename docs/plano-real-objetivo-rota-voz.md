# Plano real desta etapa: objetivo científico, sugestão de rota e voz

14/11/2026 · Ingride · cruza três documentos: [`realinhamento-reuniao-objetivo-cientifico.md`](realinhamento-reuniao-objetivo-cientifico.md) (decisão de produto do time), [`feature-02-sugestao-rotas-plano-execucao.md`](feature-02-sugestao-rotas-plano-execucao.md) e [`feature-08-voz-plano-execucao.md`](feature-08-voz-plano-execucao.md) (planos técnicos do Hugo, já em `main`)

> Objetivo deste doc: comparar o que a reunião decidiu com o que os
> planos do Hugo realmente entregam, achar os pontos onde um cobre o
> outro e onde fica faltando algo, e só então organizar a divisão de
> tarefas. Sem isso, dá pra codar os dois planos do Hugo inteiros e
> ainda não ter a feature que a reunião chamou de "o destaque central
> do projeto".

## 1. Cruzamento: o que a reunião pediu × o que o plano do Hugo entrega

| Decisão da reunião | O plano do Hugo cobre? | Como |
| --- | --- | --- |
| (2.1) Não é Waze de Marte — o sistema apoia decisão de segurança, mostra todas as rotas, inclusive as perigosas | ✅ **Sim, é o coração do plano dele** | `sugestao_rotas.py`: rótulo ✅/⚠️/⛔ por rota, **a ⛔ nunca é escondida nem bloqueada**, margem calculada pelo pior caso, não pela média |
| (2.6) IA só interpreta dado já carregado, nunca inventa | ✅ **Sim, reforçado** | Gemma restrito a uma lista fixa de destinos conhecidos; "nunca inventa coordenada" está escrito explicitamente no plano dele |
| (2.7) Visor/voz é a interface prioritária durante a caminhada, sem toque | ✅ **Sim, é o objetivo central do plano de voz** | Todo o `feature-08-voz-plano-execucao.md` é exatamente essa camada que a reunião disse que "ainda não existe" |
| (a) Coordenada por clique no mapa | ✅ Já existe (meu, feature 02) | — |
| (b) Coordenada relativa por voz ("5m ao norte") | ❌ **Não está no plano** | O plano de voz não tem essa intenção. A própria reunião já tratava isso como secundário, então não é urgente |
| (d) Comando de voz pra UI (fechar painel, abrir detalhe) | ❌ **Não está no plano** | As intenções do plano são `rota`, `sim`, `nao`, `pergunta` — nenhuma de navegação de interface |
| (2.4) Relatar obstáculo por voz e recalcular **pra frente** sem redefinir destino | ➖ **Parcialmente — e não do mesmo jeito** | O plano tem `voltar` / `emergência`, que recalcula a **volta** a partir da posição atual. Não tem uma intenção pra "tem uma rocha aqui, recalcula o caminho **até o destino que eu já tinha**" |
| **(c) Objetivo científico em texto/voz livre, sem coordenada, pra IA sugerir rotas/pontos candidatos — "destaque central do projeto"** | ❌ **Não está no plano** | Ver seção 4 abaixo — é o achado mais importante deste cruzamento |

## 2. Lista completa do que o sistema deve ter nesta etapa

Juntando os três documentos — o que já existe, o que o Hugo planejou e o
que fica de fora por decisão da própria reunião. ✅ pronto · 🔧 planejado,
a construir · 🚫 fora desta etapa (decisão já tomada, não é esquecimento.

### 2.1 Planejamento (antes de sair — tablet)

| Item | Status |
| --- | --- |
| Mapa com camadas reais (CTX/HiRISE/DTM/THEMIS), clique pra marcar ponto | ✅ |
| Painel de condições (REMS/RAD), ficha científica do ponto (F04) | ✅ |
| Rota por coordenada: 3 variantes, alertas por trecho com distância, ida+volta, O2 configurável, paradas intermediárias | ✅ (meu) |
| Campo de objetivo científico em texto livre | 🔧 **sem dono nem solução técnica ainda** — ver seção 4 |
| Objetivo científico por voz | 🔧 depende do item acima existir primeiro |
| Destino por voz usando nome exato (base, ponto marcado, um dos 3 alvos) | 🔧 Hugo, Fase 1-3 do plano de voz |
| Faixa de O2 (otimista/pessimista) por inclinação do trecho | 🔧 Hugo pede, eu implemento (Fase 1, `route_planning.py`) |
| Mapa de custo de volta a partir da base (Dijkstra) | 🔧 Hugo pede, eu implemento (Fase 2) |
| Margem mínima e ponto de não retorno por rota | 🔧 Hugo pede, eu implemento (Fase 3) |
| Rótulo ✅/⚠️/⛔ por rota, prós/contras com fonte, ordem sugerida com motivo | 🔧 Hugo, `sugestao_rotas.py` (Fase 4) |
| Confirmação por voz da rota escolhida ("vou pela rota segura" → "sim") | 🔧 Hugo, Fase 2-3 do plano de voz |

### 2.2 Durante a caminhada (visor, mãos livres)

| Item | Status |
| --- | --- |
| Captura de voz ("Guia" + fala, ou "segure espaço" como plano B) | 🔧 Hugo, Fases 1 e 4 do plano de voz |
| Pergunta livre sobre o ponto atual ("Guia, posso subir aqui?") | ✅ backend (`/api/ask`) já existe · 🔧 falta a camada de voz |
| Checkpoint de O2 informado por voz ("oxigênio 62%") → recalcula margem com taxa real, avisa se diverge do previsto | 🔧 Hugo, Fase 5 do plano de rota |
| Resposta falada de tudo (resumo de rota, resposta de pergunta, aviso de margem) | 🔧 Hugo, Fase 3 do plano de voz (saída já existe parcialmente em `web/ui/agente.js`, usada só pro `/api/ask` hoje) |
| Relatar obstáculo por voz e recalcular **pra frente** sem redefinir destino | 🚫 reunião marcou como "não prioridade imediata" — fica documentado, não esquecido |
| Coordenada relativa por voz ("5m ao norte") | 🚫 reunião tratou como secundário |
| Comando de voz pra UI (abrir/fechar painel) | 🚫 fora do escopo dos dois planos atuais |

### 2.3 Emergência

| Item | Status |
| --- | --- |
| "Guia, voltar agora" / "emergência" → 2 opções de volta a partir da posição atual (mais curta, mais suave), cada uma com tempo, O2 pessimista, inclinação máxima e fonte | 🔧 Hugo, Fase 6 do plano de rota — depende do mapa de custo de volta (2.1) estar pronto |
| Se só uma volta cabe no O2 informado, isso é dito; a outra continua aparecendo (nunca escondida) | 🔧 mesma Fase 6 |

### 2.4 Princípios que atravessam tudo (regra, não feature)

- Nenhuma rota é escondida ou bloqueada, mesmo a perigosa — quem decide é o astronauta.
- Todo número tem fonte (DTM, histórico do rover, REMS/RAD, consumo Apollo, valor informado por voz).
- Sem dado real, o campo é `null` e isso é dito em texto — nunca um valor inventado.
- Pior caso, não média, em qualquer estimativa de O2/margem.

## 3. Uso de ponta a ponta — o fluxo completo quando tudo estiver pronto

### Cenário normal (planejamento → caminhada → chegada)

1. **Antes de sair (tablet).** O astronauta abre o sistema, vê o mapa com
   as camadas reais da região. Se já sabe exatamente onde ir, clica no
   mapa. Se não sabe a coordenada mas sabe o que procura, escreve (ou
   fala) o objetivo científico — hoje restrito a escolher entre os 3
   alvos já cadastrados (ver seção 4), não a qualquer ponto do mapa.
2. O sistema calcula as rotas possíveis (segura, rápida, e científica se
   houver alvo próximo) e devolve **todas**, cada uma com rótulo
   ✅/⚠️/⛔, margem de O2 pro pior caso, ponto de não retorno e os
   prós/contras com fonte. Nenhuma é escondida.
3. A IA fala um resumo e termina em "a escolha é sua". O astronauta diz
   "Guia, vou pela rota segura" (ou escolhe clicando, se estiver no
   tablet). O sistema confirma em voz antes de ativar.
4. **Durante a caminhada (visor).** O astronauta pode perguntar a
   qualquer momento ("Guia, posso subir aqui com segurança?") e ouvir a
   resposta — o visor mostra só o essencial (veredito, distância, tempo),
   detalhe completo fica no tablet.
5. Em pontos de checkpoint, informa o oxigênio atual por voz ("Guia,
   oxigênio 62%"). O sistema recalcula a margem com a taxa real de
   consumo. Se estiver gastando mais rápido que o previsto, avisa e diz
   a nova distância até o ponto de não retorno.
6. Chegada ao destino — fim do trajeto de ida. (A volta, nesta etapa, seria
   replanejada do mesmo jeito, ou segue o card "ida + volta" se a rota
   escolhida já incluía isso.)

### Cenário de emergência (a qualquer momento da caminhada)

1. O astronauta diz "Guia, voltar agora" ou "Guia, emergência".
2. O sistema usa o mapa de custo de volta (calculado uma vez, cacheado)
   pra responder na hora, a partir da posição atual — não do destino
   planejado.
3. Oferece duas opções: a volta **mais curta** e a **mais suave** (sem
   trechos de atenção), cada uma com tempo, O2 no pior caso, inclinação
   máxima e fonte. Se só uma cabe no oxigênio informado, isso é dito, mas
   a outra continua sendo mostrada — a decisão é sempre do astronauta.
4. O astronauta escolhe por voz; o sistema confirma e ativa.

### O que esse fluxo ainda não cobre (de propósito, por decisão já tomada)

- Relatar um obstáculo físico no meio do caminho e pedir uma rota nova
  **pra frente** (não pra voltar) sem precisar redizer o destino.
- Objetivo científico realmente aberto (qualquer pergunta, qualquer
  ponto candidato) — hoje, na melhor hipótese (seção 4), seria restrito
  aos 3 alvos já cadastrados.
- Coordenada relativa por voz e comandos de voz pra UI.

## 4. O achado principal: o destaque do projeto não está em nenhum dos dois planos

A reunião foi categórica: o objetivo científico em texto livre (ex.: "quero
encontrar um tipo de mineral") é o que tira o projeto de ser "só um Waze de
Marte". Mas o plano de voz do Hugo define os destinos aceitos assim,
literalmente:

> "Destinos aceitos por voz: base, ponto marcado no mapa e os 3 alvos
> científicos do banco (Cristas de boxwork, Altadena, Totoral/Sillar). A
> lista é lida do banco, sem nome inventado. Um destino fora da lista
> recebe a resposta 'não conheço esse lugar'."

Ou seja: o astronauta pode **pedir por voz** um dos 3 alvos já cadastrados
pelo nome (ex.: "Guia, rota até Altadena") — isso já é uma forma de
objetivo. Mas ele **não pode** descrever um objetivo aberto ("quero achar
indício de água", "quero ir num lugar com crista exposta") e receber uma
sugestão de rota/ponto que a IA tenha **interpretado e escolhido** — a IA
só casa o texto contra uma lista fixa de 3 nomes próprios. É "reconhecer um
nome", não "interpretar um objetivo".

Isso não é um erro do Hugo: a decisão dele (nunca inventar coordenada) é
exatamente o princípio de honestidade de dado que o projeto inteiro segue.
O problema é que, do jeito que está, a feature "destaque central" da
reunião simplesmente não vai existir no protótipo, a não ser que alguém
decida construir a peça que falta.

### Caminho que reconcilia os dois, sem violar "nunca inventar dado"

Como só existem **3 alvos científicos cadastrados** (feature 04), dá pra
entregar uma versão honesta do objetivo científico **sem inventar
coordenada nenhuma**: em vez de a IA gerar um ponto novo no mapa, ela
**escolhe o melhor alvo entre os 3 já cadastrados**, com base no texto do
objetivo e na `medicao_curiosity`/descrição de cada um (que já existe no
banco). Ou seja:

```
"quero encontrar indício de processo hidrotermal"
  → Gemma compara contra a medicao_curiosity dos 3 alvos (já no banco)
  → escolhe o que melhor combina (ou "nenhum combina bem" -- dito, não escondido)
  → vira o `destino` de /api/route, igual um clique no mapa
```

Isso é uma versão **pequena e honesta** do que a reunião pediu: não gera
rota pra lugar nenhum que não tenha dado real, mas já tira o sistema de
"só aceita nome exato" pra "entende uma descrição e escolhe entre o que
existe de verdade". Com só 3 alvos, é pouco código: um prompt pro Gemma
com os 3 textos de `medicao_curiosity` e pedir a escolha (ou "nenhum"),
restrito a esses 3 — mesmo padrão de "saída presa a uma lista fixa" que o
Hugo já usa pro nome do destino.

**Isto é uma proposta minha, não uma decisão do time.** Precisa ser
validada com o Hugo e, idealmente, confirmada na próxima conversa com o
time todo — é exatamente o tipo de pergunta que o documento de
realinhamento já deixou em aberto ("o campo de objetivo entra nesta fase
do hackathon, ou fica só como próximo passo documentado?").

## 5. O que isso significa pro plano real desta etapa

1. **As Fases do Hugo (voz + sugestão de rota) devem seguir como estão
   planejadas** — elas implementam bem o que a reunião decidiu sobre
   segurança, pior caso e "o humano decide". Não precisam de mudança por
   causa deste cruzamento.
2. **O "objetivo científico em texto livre" continua sem dono e sem
   solução técnica definida.** A proposta da seção 4 (escolher entre os 3
   alvos já cadastrados, nunca inventar coordenada) é o caminho mais
   barato e mais honesto que encontrei, mas depende de decisão do time:
   entra agora ou fica documentado como próximo passo.
3. **O recálculo por obstáculo relatado por voz, "pra frente" sem
   redefinir destino (2.4), continua sem solução no plano do Hugo.** A
   própria reunião já disse que isso não é prioridade imediata — então
   não é uma lacuna urgente, só uma lacuna real que vale registrar.
4. **Coordenada relativa por voz (b) e comando de voz pra UI (d)
   continuam de fora**, como a reunião já esperava (tratados como
   secundários).

## 6. Divisão de tarefas

### Fica comigo (feature 02 — o motor de rota)

- `api/route_planning.py`: Fases 1 (faixa de O2 otimista/pessimista), 2
  (mapa de custo de volta via Dijkstra a partir da base) e 3 (margem por
  rota / ponto de não retorno) do plano do Hugo — ficam no meu módulo,
  entrego o contrato pronto (`margem_minima`, `ponto_nao_retorno`,
  `pior_trecho_emergencia`, `volta_minutos_max`) pro Hugo consumir.
- `web/ui/rota.js`: desenhar todas as rotas (inclusive ⛔, tracejada),
  ponto de não retorno no mapa, e trocar o card "ida + volta" (hoje uma
  simplificação que dobra o custo da ida) pelo cálculo real da Fase 2
  quando ela estiver pronta — **minha feature atual vai ser substituída,
  não vai conviver com a nova**, é bom avisar isso antes.

### Fica com o Hugo (feature 08 — voz, interpretação, sugestão)

- `api/voz.py`: transcrição (Whisper) e `interpretar()`.
- `api/sugestao_rotas.py` (novo): rótulo, prós/contras, ordem sugerida —
  só consome o que `route_planning.py` passar a devolver.
- `web/ui/voz.js` + `voz-captura.js`: captura de áudio e estados.
- `api/agente.py`: bloco ROTAS no contexto do Gemma.
- **Se o time aprovar a proposta da seção 4**: a escolha de alvo
  científico por objetivo em texto provavelmente fica com ele também,
  porque usa o mesmo Gemma e o mesmo padrão de "saída presa a uma lista"
  que ele já implementa pro nome do destino.

### Decisão de time, não cabe a nenhum de nós sozinho

- Limite de folga de O2 pra ⚠️/⛔ (sem fonte oficial, vira "proposta H2G2"
  documentada como tal).
- Variante `mais_direta` que permite trecho acima de 20° de propósito (pra
  existir uma rota ⛔ de verdade na lista) — muda o comportamento do A*,
  não só a exibição.
- **A proposta da seção 4** (objetivo científico "lite", restrito aos 3
  alvos cadastrados): entra nesta fase ou vira próximo passo documentado?
- O recálculo por obstáculo "pra frente" (2.4): prototipar sem voz
  primeiro (um botão no mapa), ou deixar fora do protótipo atual?

## 7. Antes de eu codar qualquer coisa deste plano

Preciso alinhar com o Hugo os três pontos de atrito de arquivo
(`route_planning.py` e `rota.js` sendo mexidos pelos dois planos) e levar
as quatro perguntas da seção 4 pro time, pra não haver dois PRs
conflitantes no mesmo dia nem retrabalho se a resposta for "isso fica pra
depois".
