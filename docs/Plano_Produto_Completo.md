# DETON8 · Plano de Produto — Martian Map (H2G2)

Nov 8, 2026 · @vic

## 1. O desafio e a nossa tese

**Decisão proposta:** construir o H2G2 como um guia de campo hiperlocal para uma Marswalk na região de boxwork do Monte Sharp (Cratera Gale), com o mapa como núcleo e o "modo traje" (visor + voz offline) como diferencial de pitch.

**O que a NASA pede.** O site oficial bloqueia leitura automática, então o enunciado foi reconstruído a partir das notas da Victoria e de times que já o citam. Pede-se um mapa em camadas de um local ou rota em Marte, combinando dados de várias missões científicas, que ajude o astronauta em três frentes: rota e destinos, condições atuais e ciência ao longo do caminho ([resumo do enunciado](https://github.com/lkorth/mars-traverse)). O exemplo do próprio enunciado é o boxwork estudado pelo Curiosity em 2025 no Monte Sharp. A crítica central: Mars Trek e o mapeamento geológico USGS-NASA servem visões globais e regionais, não a escala de metros de uma caminhada.

**Por que boxwork em Gale, e não Jezero.** Encontrei mais de uma dúzia de repositórios públicos de 2026 neste desafio, a maioria um "planejador de Marswalk em Jezero com A*, slope e O₂" ([exemplo 1](https://github.com/AhsanulHoque22/Nasa-Space-Apps-Challenge-2026-Team-Protikriti), [exemplo 2](https://github.com/leo-noble/RedStep), [exemplo 3](https://github.com/lkorth/mars-traverse)). Jezero virou commodity. Gale/boxwork é o exemplo citado pela NASA, tem dado in-situ único (radiação RAD e clima REMS do Curiosity no mesmo local) e ciência recente: cristas de 1 a 2 m com areia entre elas, argila nas cristas e carbonato nas depressões, e nódulos de água subterrânea ([NASA, fev/2026](https://www.nasa.gov/missions/mars-science-laboratory/curiosity-rover/NASAs-curiosity-rover-sees-martian-spiderwebs-up-close/)). Os próprios operadores relatam risco de patinar na areia das depressões, o que é um caso de segurança operacional pronto para o pitch.

**Como seremos julgados.** Cada feature abaixo é pontuada contra os 5 itens que o mentor destacou: Localização (L), Integração científica (I), Segurança operacional (S), Contexto científico (C) e Uso demonstrado de dados abertos (D). Projeto sem uso real de dados é eliminado, mesmo com pitch bom.

## 2. Ideias da Victoria, organizadas e priorizadas

As ideias viram 10 features, na ordem em que devem ser construídas. P0 entra no MVP de sábado; P1 é diferencial se o P0 estiver de pé até domingo cedo; P2 vai só para o pitch. Itens: L, I, S, C, D (seção 1).

| # | Feature (ideia original) | Prioridade | Complexidade | Itens | Fontes | Viabilidade e ganho |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Mapa hiperlocal em camadas do boxwork: imagem, relevo, inclinação, mineralogia, geologia | P0 · MVP | Média | L I D | HiRISE e CTX via Mars Trek; DTM HiRISE 1 m de Gale; CRISM | Viável: Gale já tem terreno de 1 m e HiRISE colorido de 25 cm ao longo do trajeto do Curiosity. É o ponto de corte da banca; sem ele nada pontua. |
| 2 | Rota inteligente + indicadores de risco (must) | P0 · MVP | Alta | S I D | DTM → slope; AI4Mars e textura HiRISE para areia; RAD; limites Artemis | A* numa grade de 2 a 5 m cobre poucos km² em um dia. Custo = inclinação (corte em 20°, referência Artemis), areia nas depressões, dose e O₂. Todos fazem rota; nosso diferencial é o risco de areia entre cristas, específico do boxwork. |
| 3 | Clique no ponto → fotos reais próximas (rover e órbita), com distância e direção | P0 · MVP | Média | C D L | API de imagens brutas do MSL; posições MMGIS; Photojournal | Viável: cada imagem do Curiosity traz sol, site e drive, que o MMGIS liga a coordenadas. Pré-baixar ~200 imagens do boxwork resolve offline. Ganho alto e raro entre concorrentes. |
| 4 | Ficha científica do ponto (estilo "pokédex") | P0 · MVP | Média | C I | Resultados CheMin/APXS do Curiosity; CRISM; AI4Mars; nomenclatura IAU/USGS | Identificar mineral por foto não é confiável. A ficha mostra o que foi medido: argila nas cristas, carbonato nas depressões, mineral orbital e classe de terreno. Versão curada com 8 a 10 alvos. |
| 5 | Painel de condições: clima, radiação, sol, poeira | P0 · MVP | Baixa | S D | REMS e RAD (PDS); algoritmo Mars24; climatologia de poeira LMD | Séries públicas e leves. Gale é o único ponto com radiação medida na superfície. Cobre "condições atuais" do enunciado. |
| 6 | Previsão climática local offline | P1 · Diferencial | Média | S | Série REMS desde 2012 | Já existe: rede neural prevê o sol seguinte com dados REMS ([de Cabo-García et al.](https://ui.adsabs.harvard.edu/abs/2019EGUGA..2111304D/abstract)). Usamos como base citada, não como invenção: climatologia por estação (Ls) + ajuste pelo último sol. |
| 7 | Visor no traje (HUD) + protótipo Blender | P1 · Diferencial | Média | S L | Requisitos NASA SUITS 2024 (cenário Marte) | Web "modo traje" com minimapa 2D, trilha de retorno, pins e alertas, como pede o [SUITS](https://nasa.gov/wp-content/uploads/2023/09/fy24-suits-mission-description.pdf). Blender só para o render do pitch; hardware real fora de escopo. |
| 8 | Assistente de voz offline | P1 · Diferencial | Alta | C S | LLM local pequeno + busca no nosso pacote de dados; reconhecimento de voz local | Roda num notebook com modelo de 1 a 4 B quantizado. Tom profissional: responde só com o pacote, cita fonte e confiança, nunca decide pela tripulação. Ter vídeo de backup para o pitch. |
| 9 | Base local 2026 + sincronização Terra–Marte | P2 · Visão | Baixa | D | Pacote offline próprio | Pacote offline é simples e entra no MVP. Sync real vira estudo à parte: atraso de 3 a 22 min por trecho ([NASA Ames](https://www.nasa.gov/ames/core-area-of-expertise-intelligent-and-adaptive-systems/)). Na demo, botão "sincronizar" com atraso simulado. |
| 10 | Captação contínua de imagens de rovers | P2 · Visão | Baixa | C | Mesmas da #3 | Rover batedor fotografa a rota antes do astronauta. Só narrativa; o MVP reaproveita a #3. |

A ideia de estudar mapas da Lua virou tarefa de pesquisa e gerou as features 11 e 12 da próxima seção. O branding H2G2 está na seção 5.

## 3. Fontes de dados: martelo batido

**Espinha:** Mars Trek para imagens em tiles, USGS/PDS para rasters pesados, MMGIS e API do MSL para o rover. Na sexta, cada linha é conferida contra a aba Resources; o que vier lá substitui o equivalente daqui.

| Camada | Fonte (missão · instrumento) | Resolução | Acesso | Usada em |
| --- | --- | --- | --- | --- |
| Imagem de detalhe | MRO · HiRISE colorido ao longo do trajeto do Curiosity | 25 cm | Mars Trek (tiles) | #1, #3 |
| Imagem de contexto | MRO · CTX, mosaico global | ~6 m | Mars Trek / Esri | #1 |
| Relevo local | DTM HiRISE de Gale | 1 m | USGS Astrogeology / PDS | #1, #2, #11, #16 |
| Relevo regional | MGS · MOLA + ESA Mars Express · HRSC (blend) | 200 m | USGS | 3D, contexto |
| Mineralogia | MRO · CRISM (sulfatos, argilas) | ~18 m | PDS / Mars Trek | #1, #4 |
| Classe de terreno | [AI4Mars](https://openaccess.thecvf.com/content/CVPR2021W/AI4Space/papers/Swan_AI4MARS_A_Dataset_for_Terrain-Aware_Autonomous_Driving_on_Mars_CVPRW_2021_paper.pdf): solo, rocha-mãe, areia, rocha grande, em ~35 mil imagens do Curiosity | por pixel | JPL / Hugging Face | #2, #4 |
| Trajeto e posição | MMGIS (Curiosity) | por parada | mars.nasa.gov | #3, #13 |
| Fotos do rover | API de imagens brutas do MSL + Photojournal | por imagem | mars.nasa.gov | #3 |
| Clima | MSL · REMS | várias leituras por sol | PDS Atmospheres | #5, #6 |
| Radiação | MSL · RAD | série contínua desde 2012 | PDS | #2, #5 |
| Poeira sazonal | Climatologia de poeira LMD (parceiros CNES/ESA) | global | LMD | #5 |
| Sol e horário | Mars24 (NASA GISS) | cálculo | algoritmo público | #5, #16 |
| Nomes | Gazetteer USGS / IAU | — | planetarynames | #1 |
| Gelo raso | SWIM (PSI) | — | swim.psi.edu | Só contexto: Gale é equatorial, então mostramos "sem gelo acessível" com honestidade |

## 5. Escopo, decisões e riscos

**Escopo por marco.** Sábado 23h: features 1, 2, 3, 4 (curada), 5, 11, 13 e 17 rodando offline num notebook. Domingo manhã: 7 (modo traje web), 6, 12 e, se o P0 estiver estável, 8. Só no pitch: 9, 10, 18 e o render Blender do visor.

**Decisões para o time fechar até sexta:**

- **Branding.** "The Hitchhiker's Guide to the Galaxy" é marca registrada de Douglas Adams, inclusive para software ([registro](https://trademark.justia.com/owners/adams-douglas-643862)). O risco num hackathon sem fins comerciais é baixo, mas título, logo e capa são dispensáveis. Proposta: manter a sigla H2G2 com significado próprio (ex.: Human-to-Ground Guide) e usar "não entre em pânico" só como piscadela no pitch. O nome do desafio já faz a referência por nós.

- **Local.** Gale/boxwork é o recomendado; Jezero fica como plano B se os Resources só trouxerem Jezero.

- **IA de voz.** Entra só se houver uma pessoa dedicada desde sexta. Sem isso, vira vídeo no pitch.

- **Visor.** Um render e um vídeo curto no Blender; nenhum hardware.

**Riscos e mitigação.** Rasters de 1 m pesam GB: recortar uma área de ~3 × 3 km e testar o pipeline com um recorte de exemplo até sexta, integrando o definitivo só após a liberação dos Resources. Internet no local só no sábado: pacote offline pronto antes. Demo ao vivo pode travar: gravar o tour de 3 minutos no domingo.

## Fontes

- [NASA: Curiosity e o boxwork do Monte Sharp](https://www.nasa.gov/missions/mars-science-laboratory/curiosity-rover/NASAs-curiosity-rover-sees-martian-spiderwebs-up-close/) (fev/2026)

- [NASA SUITS 2023–2024: descrição da missão em Marte](https://nasa.gov/wp-content/uploads/2023/09/fy24-suits-mission-description.pdf)

- [NASA: conceito de operações de EVA lunar (Artemis)](https://www.nasa.gov/wp-content/uploads/2020/01/topic_1-_eva_lunar_surface_concept_of_operations.pdf)

- [NASA: planejamento de EVAs lunares e AEGIS](https://ntrs.nasa.gov/api/citations/20250006988/downloads/ASCEND%20presentation%20-%20Planning%20Lunar%20EVAs.pdf)

- [NASA Ames: atraso de comunicação e operação autônoma](https://www.nasa.gov/ames/core-area-of-expertise-intelligent-and-adaptive-systems/)

- [AI4Mars (JPL, CVPR 2021)](https://openaccess.thecvf.com/content/CVPR2021W/AI4Space/papers/Swan_AI4MARS_A_Dataset_for_Terrain-Aware_Autonomous_Driving_on_Mars_CVPRW_2021_paper.pdf)

- [Previsão do tempo em Marte com redes neurais e REMS](https://ui.adsabs.harvard.edu/abs/2019EGUGA..2111304D/abstract)

- [Registro de marca de Douglas Adams](https://trademark.justia.com/owners/adams-douglas-643862)

- Concorrentes 2026 analisados: [Mars Traverse](https://github.com/lkorth/mars-traverse), [Martian Map · Protikriti](https://github.com/AhsanulHoque22/Nasa-Space-Apps-Challenge-2026-Team-Protikriti), [RedStep](https://github.com/leo-noble/RedStep), [ARES//NAV (boxwork)](https://github.com/SinuraWahalathanthri/ares-nav-martian)

O site oficial do Space Apps bloqueia leitura automática; o enunciado foi reconstruído a partir das notas da Victoria e de repositórios que o citam. Conferir a página oficial antes de sexta.