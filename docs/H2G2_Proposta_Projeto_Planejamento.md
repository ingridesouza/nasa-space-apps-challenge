

| NASA SPACE APPS SALVADOR 2026 · INTERPLANETARY SURVIVAL GUIDE: MARTIAN MAP H2G2   Human-to-Ground Guide Guia de campo hiperlocal para uma caminhada segura em Marte na região de boxwork do Monte Sharp, Cratera Gale. TIME DETON8 · PLANO DE PRODUTO · NOVEMBRO DE 2026 |  |
| :---- | :---- |
|  |  |

| Nome tirado de The Hitchhiker's Galaxy Guide (Guia do Mochileiro das Galáxias) abreviação matemática: H2G2 |
| :---- |

 **01   Qual será nosso ambiente experimental**

a NASA já tem os meios para mapas macro; a inovação está em um protótipo de uma região específica, rica em dados, com objetivo claro e experiência aprofundada.

**Por que Gale e não Jezero (região mais famosa)**

* **Concorrência:** mais de 12 repositórios públicos de 2026 neste desafio.

* **Aderência:** o boxwork é o exemplo citado pela própria NASA.

* **Dado único:** Gale é o único local com radiação (RAD) e clima (REMS) medidos no mesmo ponto da superfície.

* **Ciência recente:** cristas de 1 a 2 m com areia entre elas, argila nas cristas, carbonato nas depressões e nódulos de água subterrânea, sinal de que a água durou mais do que se pensava.

* **Risco citável:** os operadores do Curiosity relatam risco de patinar na areia das depressões, um caso real de segurança operacional.

* **Plano B:** Jezero, se os Resources de sexta trouxerem só Jezero.

**Como o produto é usado**

* **Durante:** O visor mostra a rota e os alertas, e a voz responde dúvidas sem depender da Terra.

* **Sempre:** tudo roda sobre a base local e com dados preditivos, que se atualizam quando há janela de contato com a Terra.

 **02   As features do H2G2**

**■□□ BAIXA**  **■■□ MÉDIA**  **■■■ ALTA**   complexidade


**A · Núcleo do mapa**

|    01   Mapa hiperlocal em camadas do boxwork \- Ingride  P0 · MVP   ■■□ MÉDIA    *Ideia original: mapa visto de cima, com relevo e indicadores térmicos, climáticos e geológicos; camadas ópticas, térmicas, espectrais, topográficas, geofísicas, atmosféricas, de radiação e químicas.* O que é: o coração do H2G. Uma área de \~3 × 3 km do boxwork no Monte Sharp, com zoom contínuo do contexto regional (CTX, \~6 m) até o detalhe de 25 cm (HiRISE). Cada camada liga, desliga e tem opacidade ajustável. Entram 7 das 8 categorias: óptica (HiRISE, CTX), topográfica (relevo de 1 m \+ inclinação), espectral e química (CRISM: sulfatos e argilas; medições do Curiosity como pontos), térmica (THEMIS, Mars Odyssey), atmosférica e radiação (REMS e RAD). Fica de fora: geofísica. Não há dado orbital útil na escala de metros do boxwork; dizer isso com clareza vale mais que forçar uma camada. Viabilidade: alta. Gale já tem relevo de 1 m e HiRISE colorido ao longo do trajeto do Curiosity, servidos pelo Mars Trek e pelo USGS/PDS. Ganho: é o ponto de corte da banca. Sem dados reais integrados aqui, nenhuma outra feature pontua.  |
| :---- |

|    02   Rota inteligente \+ indicadores de risco \- Hugo   P0 · MVP   ■■■ ALTA   *Ideia original: análise inteligente de melhor rota (must) e indicadores de risco inteligentes.* Como funciona: o astronauta marca origem, paradas e destino. O sistema calcula a rota por A\* sobre a grade de relevo (2 a 5 m) e devolve três opções: mais segura, mais rápida e mais ciência (passa pelos alvos da feature 4). Custo de cada trecho: inclinação, rochas e rugosidade, areia, exposição à radiação, tempo e O₂ consumido. Motor do orçamento de O₂: o A\* calcula o gasto de oxigênio de cada trecho de forma dinâmica, cruzando a distância com o esforço físico (inclinação do DTM mais rugosidade e areia do AI4Mars) e comparando o resultado com o nível de O₂ do traje. Na demo, o nível do traje é simulado. Indicadores na tela: trechos coloridos por risco, perfil de elevação, distância, tempo estimado, O₂ gasto e o motivo de cada alerta. Inclinação acima de 20° (limite de caminhada usado pelo Artemis) vira alerta vermelho. Risco típico do boxwork: areia nas depressões entre as cristas. Os operadores do Curiosity relatam risco de as rodas patinarem ali, e as cristas funcionam como “estrada”. Ganho: máximo em segurança operacional. Quase todos os concorrentes têm rota; o diferencial é o risco específico do terreno e a explicação de cada alerta.  |
| :---- |

**B · Contexto científico**

|   03   Clique no ponto → fotos reais próximas, com distância e direção \- Victoria  P0 · MVP   ■■□ MÉDIA    *Ideia original: ao clicar num ponto, mostrar as imagens disponíveis da região com indicadores como a distância até o ponto. Propor também captar imagens de rovers.* Como funciona: o clique busca fotos do Curiosity tiradas num raio de até \~200 m e lista miniaturas por distância: “140 m · olhando para NE · sol 4650 · Mastcam”. Junto, o recorte orbital HiRISE do mesmo ponto. Pipeline: a API de imagens brutas do MSL traz sol, site, drive e câmera de cada foto; o MMGIS liga site e drive a coordenadas. Um índice local com \~200 fotos do boxwork roda offline. Cuidado de honestidade: a posição é de onde a foto foi tirada, não do que ela mostra. A interface diz “tirada a 140 m daqui”. Evolução (captação de rovers): um rover batedor fotografa a rota antes do astronauta e alimenta o mesmo índice. Fica para o pitch. Ganho: alto e raro entre concorrentes; liga dado orbital e de superfície no mesmo clique.  |
| :---- |

|    04   Ficha científica do ponto (estilo “pokédex”) \- Victoria  P0 · MVP   ■■□ MÉDIA *Ideia original: interface intuitiva de jogo, com modais; cruzar a imagem de um ponto com fontes públicas confiáveis para dizer quais rochas são aquelas.* Ajuste necessário: identificar mineral só pela foto não é confiável e a banca percebe. A versão profissional mostra o que já foi medido e por quem. O que o cartão traz: medição local do Curiosity (argila nas cristas, carbonato nas depressões), mineral visto de órbita (CRISM), classe de terreno (AI4Mars: solo, rocha-mãe, areia, rocha grande), nome oficial IAU/USGS e por que importa (água subterrânea, habitabilidade). Experiência: modal que abre e fecha, ícone por tipo de alvo, nível de confiança e link para a fonte original. Preparo antes do evento: estruturar 8 a 10 alvos do boxwork a partir das notícias e do blog do Curiosity e do PDS. Ganho: cobre o critério de contexto científico e alimenta a rota “mais ciência”.  |
| :---- |

**C · Condições e autonomia**

|    05   Painel de condições: clima, radiação, sol e poeira  P0 · MVP   ■□□ BAIXA  *Ideia original: indicadores térmicos, climáticos, atmosféricos e de radiação no mapa.* O que mostra: temperatura do ar e do solo, pressão, vento e UV (REMS); dose de radiação (RAD); hora solar local, nascer, pôr e altura do Sol (Mars24); opacidade de poeira esperada para a estação (LMD). Contexto: tudo para a data e a hora escolhidas da EVA. Gale é o único ponto de Marte com radiação medida na superfície. Ganho: responde à frente “condições atuais” do enunciado com séries públicas e leves.  |
| :---- |

|    06   Previsão climática local offline  P1 · DIFERENCIAL   ■■□ MÉDIA  *Ideia original: análise preditiva dos fenômenos climáticos, local no hardware, para suprir a falta de comunicação com a Terra; pesquisar se já existe.* Resultado da pesquisa: já existe. Uma rede neural treinada com dados REMS prevê o sol seguinte com erro de 0,5 a 1% nas variações diurnas de temperatura e pressão (de Cabo-García et al.). Como usamos: como base citada, não como invenção. Modelo leve embarcado: climatologia por estação (Ls) \+ correção pelo último sol medido. Onde está a inovação: rodar no traje ou no habitat, sem Terra, e acoplar a previsão à rota, sugerindo a melhor janela para a EVA. Ganho: médio em pontos, forte na narrativa de autonomia. Prever temperatura e pressão do sol seguinte e comparar com dado real guardado.  |
| :---- |

|   09   Base local 2026 \+ sincronização Terra–Marte  P2 · PITCH   ■□□ BAIXA   *Ideia original: extrair dados de 2026 da região e guardá-los localmente; o diferencial é atualizar via comunicação Marte–Terra, com estudo de viabilidade à parte (tempo de resposta, fenômenos periódicos).* Base local (entra no MVP): pacote offline com camadas, relevo, fichas, fotos e séries climáticas. É simples e resolve também a falta de internet no evento. Estudo de viabilidade: o atraso é de 3 a 22 min em cada sentido, com poucas janelas de contato por sol via orbitadores. Fenômenos periódicos que cortam ou degradam o contato: a conjunção solar, quando Marte fica atrás do Sol por semanas, e as tempestades de poeira sazonais. Proposta: sincronizar por pacotes de diferença, com prioridade: alertas, depois clima, depois imagens. Na demo: botão “sincronizar” com atraso simulado e lista do que mudou.  |
| :---- |

|   10   Perigos colaborativos  P2 · PITCH   ■■■ ALTA   *Conceito de pitch: como no Waze, o astronauta reporta perigos do terreno que a órbita não enxerga e o mapa passa a mostrá-los para todos.* O que é: O astronauta marca por voz anomalias de terreno que não aparecem nas imagens de órbita, como “areia fofa aqui”. A voz é a entrada natural com luvas (feature 7). Como funciona: o risco marcado adiciona uma penalidade de custo no grafo do A\* (feature 2\) e dispara o recálculo imediato da rota, com a mensagem “Recalculando com explicação”. Para a equipe e para a Terra: na sincronização seguinte (feature 9), o perigo sobe como uma nova camada do mapa, visível à equipe e à Terra. Status: conceito e narrativa de pitch, apresentados como visão de produto; fora do MVP. Ganho: fecha a história do pitch: a órbita mostra o terreno de cima, e quem está no chão acrescenta o que só se percebe caminhando.  |
| :---- |

**D · Interface no traje**

|    07   Visor no traje (HUD) \+ protótipo no Blender  P1 · DIFERENCIAL   ■■□ MÉDIA *Ideia original: mapa no visor do traje, com microfone embutido; parte da equipe só para idealizar, analisar a viabilidade técnica e fazer um protótipo visual no Blender.* Referência oficial: o desafio estudantil NASA SUITS 2024 (cenário Marte) pede no visor minimapa 2D, pontos de interesse, trilha de volta (“breadcrumb”), pins, alertas de telemetria e dados de amostra, motivado por atraso de até 20 min com a Terra. Entrega no hackathon: uma tela web “modo traje” com o layout do HUD e um render ou vídeo curto do capacete no Blender. Estudo de viabilidade técnica: óculos de realidade aumentada com passthrough (o SUITS usa HoloLens 2 e Magic Leap), leitura sob luz solar forte e luvas que inviabilizam toque, o que torna a voz a entrada principal. Ganho: alto em apresentação; mostra o produto nas mãos de quem vai usá-lo.  Modo traje com minimapa, rota ativa e alertas; hardware fora de escopo.  |
| :---- |

|    08   Assistente de voz offline  P1 · DIFERENCIAL   ■■■ ALTA   *Ideia original: IA leve, embutida localmente, que lide com grande volume de dados e tire dúvidas do astronauta por áudio, de forma profissional e não sensacionalista.* Como funciona: reconhecimento de voz local → modelo de linguagem pequeno (1 a 4 bilhões de parâmetros, quantizado) → busca no pacote de dados do H2G → resposta curta falada e na tela. Regras que o tornam profissional: responde só com o pacote, cita a fonte e o nível de confiança, diz “não sei” quando não sabe, usa linguagem de procedimento e nunca decide pela tripulação. Precedentes: NASA e Google testam um assistente médico para tripulações (CMO-DA); ESA e CNES desenvolvem o AMAIA, assistente que funciona sem internet. Exemplos: “Qual a inclinação do próximo trecho?” · “O que é esta rocha?” · “Como está a poeira hoje?” Risco: travar ao vivo. Gravar um vídeo de backup.  |
| :---- |

 **03   Pesquisas de apoio obrigatórias**

* **Mars Trek e mapeamento USGS-NASA:** o Mars Trek é o portal do JPL que reúne, já alinhados, dados de várias missões e foi ampliado para apoiar a escolha de locais de pouso humano. O programa USGS-NASA produz os mapas geológicos oficiais dos corpos planetários. Ambos trabalham na escala regional e global; o H2G ocupa a escala de metros.

* **Mapas da Lua:** o Artemis planeja caminhadas em inclinações de até 20° e a até 2 km do módulo. O sistema de mapas de EVA do Artemis (AEGIS) gera um caderno de mapas e um checklist de punho. Lição: o que chega ao astronauta é simples e direto, e isso guia o modo traje.

* **Previsão climática:** já existe base acadêmica sólida (feature 6). Usamos e citamos.

 **04   Fontes dos dados de cada Feature**

Espinha: Mars Trek para imagens, USGS/PDS para relevo e espectros, MMGIS e API do MSL para o rover. Sexta à noite, cada linha é conferida com a aba Resources; o que vier lá substitui o equivalente.

| CAMADA | FONTE · MISSÃO · ACESSO | RESOLUÇÃO | FEATURES |
| :---- | :---- | :---- | :---- |
| **Imagem de detalhe** | MRO · HiRISE colorido no trajeto do Curiosity · Mars Trek | 25 cm | 1, 3 |
| **Imagem de contexto** | MRO · CTX, mosaico global · Mars Trek | \~6 m | 1 |
| **Relevo local** | DTM HiRISE de Gale · USGS Astrogeology / PDS | 1 m | 1, 2 |
| **Relevo regional** | MGS · MOLA \+ ESA Mars Express · HRSC · USGS | 200 m | 1 |
| **Mineralogia** | MRO · CRISM (sulfatos, argilas) · PDS / Mars Trek | \~18 m | 1, 4 |
| **Térmica** | Mars Odyssey · THEMIS infravermelho · Mars Trek | 100 m | 1 |
| **Classe de terreno** | AI4Mars (JPL), \~35 mil imagens do Curiosity | pixel | 2, 4 |
| **Trajeto e posição** | MMGIS do Curiosity · mars.nasa.gov | parada | 3 |
| **Fotos do rover** | API de imagens brutas do MSL \+ Photojournal | imagem | 3 |
| **Clima** | MSL · REMS · PDS Atmospheres | várias/sol | 5, 6 |
| **Radiação** | MSL · RAD · PDS, série desde 2012 | diária | 2, 5 |
| **Poeira sazonal** | Climatologia de poeira LMD (parceiros CNES/ESA) | global | 5 |
| **Sol e horário** | Mars24 (NASA GISS) | cálculo | 5 |
| **Nomes** | Gazetteer USGS / IAU | — | 1, 4 |
| **Gelo raso** | SWIM (PSI): só contexto, Gale é equatorial | — | 1 |

