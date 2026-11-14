# Realinhamento do objetivo do projeto — reunião de time

14/11/2026 · transcrito de áudio (duas gravações), organizado por Claude a pedido de Ingride.

> **Aviso sobre a fonte**: este documento vem de transcrição automática de
> áudio de reunião, bastante ruidosa em trechos (frases cortadas, palavras
> trocadas). Separei "o que foi dito" (o mais próximo possível do que a
> transcrição realmente registra) de "o que entendemos que vira projeto"
> (interpretação, pra validar com o time). Onde ficou ambíguo, marquei
> como tal — não completei lacuna nenhuma com suposição.

## 1. Por que essa reunião aconteceu

O gatilho foi uma pergunta direta feita no meio da conversa: **"isso que
estamos construindo é um Google Maps / Waze de Marte?"** A resposta do
time foi "não deveria ser", e a reunião girou em torno de reafirmar qual
é o diferencial real do H2G2 frente a só calcular rota A→B.

## 2. O que foi dito

### 2.1 Rejeição do framing "Waze de Marte"

O consenso foi que o objetivo central do sistema é **apoiar a decisão de
segurança do astronauta** (chegar vivo e voltar vivo), não otimizar
distância/tempo como um app de trânsito. A rota em si é meio, não fim.

### 2.2 Quatro formas discutidas de definir pra onde o astronauta vai

| # | Forma | Como foi descrita | Status discutido |
|---|---|---|---|
| a | Coordenada por clique ou digitação no mapa | Astronauta já sabe o ponto exato (vindo de estudo prévio, dado do rover, ou coordenada passada pela base/NASA) | Já existe e funciona (feature 02 atual) |
| b | Coordenada relativa por voz | "Quero ir 5m ao norte, 5m a leste" a partir da posição atual — considerada mais intuitiva que digitar lat/lon dígito por dígito | Ideia, não implementada; tratada como secundária |
| c | Objetivo científico em texto ou voz livre | Ex.: "quero encontrar tal tipo de mineral" — sem coordenada nenhuma. A IA interpreta o texto, cruza com os dados já carregados localmente e sugere rotas/pontos candidatos pro astronauta escolher | **Definido como o destaque central do projeto** |
| d | Comando de voz pra interface | "Fechar esse painel", "abrir detalhes" — não é sobre rota, é sobre operar a tela sem usar as mãos (luvas do traje) | Separado das outras três; é usabilidade/acessibilidade, não roteamento |

### 2.3 Decisão de arquitetura: o objetivo vem antes e envolve o destino

Ponto debatido e fechado: o objetivo científico **não é uma quarta opção
isolada** ao lado da coordenada — ele **precede e contextualiza** a
escolha de destino, mesmo quando esse destino acaba sendo uma coordenada
fixa.

Exemplo dado na reunião: o astronauta pode ter uma coordenada exata vinda
da NASA, mas se ele também informou o objetivo da missão, a IA pode
sugerir (ou o astronauta pode justificar) atravessar uma área
tecnicamente arriscada porque ele **tem equipamento específico pra
aquilo** — ou seja, a rota "ótima" depende do objetivo e do equipamento,
não só do relevo bruto.

Frase chave (parafraseada): *"até eu chegar na coordenada, eu já usei a
parte do objetivo — então quando eu marco a coordenada, o sistema já sabe
quem eu sou e o que estou fazendo ali."*

### 2.4 Recálculo de rota por obstáculo relatado por voz

Cenário discutido: o astronauta encontra um obstáculo não previsto
(ex.: rocha grande no caminho). Decisão: **ele não deve ter que redefinir
o destino do zero** — ele só relata o obstáculo (por voz), e o sistema
recalcula a partir da posição atual até o destino B que já era conhecido,
mostrando as opções pra ele decidir. A decisão final de qual rota seguir
continua sendo do astronauta, nunca automática.

Marcado como importante, mas **não prioridade imediata** — citado como
algo pra não fugir do escopo com o tempo disponível.

### 2.5 Fora de escopo, reafirmado

- Previsão/extrapolação de terreno fora da área já mapeada ("desconhecida
  do planeta") — julgado que consome tempo demais pro protótipo atual.
  (Isso já havia sido descartado numa conversa anterior deste mesmo
  projeto, fora da reunião transcrita.)

### 2.6 Princípio de dado local reforçado

Foi reafirmado que a IA **só interpreta dado que já foi carregado
localmente no sistema** — ela não busca nada fora disso. Isso é
consistente com o que já está escrito no `CLAUDE.md` do repositório
(offline-first, zero chamada externa em tempo de execução) — a reunião
não mudou esse princípio, só o confirmou pro caso específico do campo de
objetivo.

Houve uma discussão paralela, sem decisão técnica fechada, sobre o
tamanho do modelo de IA embarcado ("IA leve" vs. carregar mais dado pra
ter respostas mais assertivas) — ficou em aberto, é mais uma preocupação
de produto/custo do que uma diretriz de arquitetura.

### 2.7 Interface: visor vs. tablet, comando por voz

- O **visor** (acoplado ao capacete) foi definido como prioridade durante
  a caminhada, porque as mãos do astronauta estão ocupadas pelo traje.
- O **tablet** serve principalmente pro planejamento antes de sair em
  missão.
- Foi cogitado um "tablet de pulso" como alternativa mais futurista, sem
  decisão fechada.
- Interação é só por comando de voz — "ele não precisa tocar, só precisa
  comandar". A IA pode responder tanto em texto/visual quanto em voz.
- Restrição de UX citada: o campo de visão do visor precisa ficar limpo
  (terreno desconhecido sob os pés) — informação essencial sempre
  visível, detalhe adicional só quando pedido.
- O time reconheceu explicitamente que **essa camada de voz/visor ainda
  não existe** no projeto, e que a prioridade antes de expandir pra ela é
  entregar bem a base que já está pronta (mapa, rota, ficha do ponto).

## 3. O que isso muda no projeto — síntese pra validar

Isto é interpretação, não transcrição — por favor confirmem ou corrijam:

1. **Nada do que já foi construído fica obsoleto.** A rota A\* por
   coordenada (feature 02, o que tenho implementado) continua sendo a
   base técnica. A reunião não pediu pra refazer isso — pediu pra **somar
   uma camada de objetivo em texto por cima dela**.
2. **O campo de objetivo científico parece pertencer à fronteira entre a
   feature 02 (rota) e a feature 08 (agente local)**: a feature 08 já tem
   um motor de interpretação de linguagem (`api/agente.py`), e a sugestão
   de rota por objetivo provavelmente usaria esse motor pra decidir
   *para onde* sugerir rota, entregando o destino resultante pro mesmo
   A\* que já existe. **Isso não ficou explicitamente atribuído a uma
   pessoa na reunião transcrita.**
3. **O "recálculo por obstáculo relatado por voz" depende de três coisas
   que ainda não existem**: entrada de voz, um jeito de o astronauta
   descrever o que está vendo, e uma função que já existe parcialmente
   (A\* recalculando origem→destino) — o pedaço novo é só a UX de
   "reportar sem redigitar destino".
4. **Voz e visor são trabalho de interface, não de lógica de rota** — o
   que já construí em `web/ui/rota.js` continua válido como o conteúdo
   que, no futuro, seria também lido em voz alta ou resumido no visor.

## 4. Perguntas em aberto (precisam de decisão do time, não minha)

- Quem fica com o campo de objetivo científico: é uma extensão da
  feature 02, da feature 08, ou uma feature nova?
- O campo de objetivo entra nesta fase do hackathon, ou fica só como
  "pitch"/próximo passo documentado (como já tratamos a análise
  preditiva de terreno desconhecido)?
- A ideia de "coordenada relativa por voz" (5m norte, 5m leste) tem
  prioridade real, ou é só uma nota de usabilidade pra depois?
- O recálculo por obstáculo relatado por voz: vale prototipar uma versão
  sem voz primeiro (ex.: um botão "reportar obstáculo aqui" no mapa, que
  já recalcula a partir da posição atual) pra testar a lógica antes de
  depender de reconhecimento de voz?
