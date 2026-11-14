# Raio-x: H2G2 contra o plano do produto (PDF DETON8)

Feito em 14/11/2026 e revisado no mesmo dia por três verificações independentes. Compara o sistema rodando com a promessa do `H2G2_NasaSpaceApps_DETON8.pdf`, do `CLAUDE.md` e dos docs de feature. Cada achado foi conferido no sistema; o que não deu para conferir está em "A confirmar".

**Veredito:** mapa, rota, ficha, fotos e previsão rodam offline com dado real. Os maiores riscos são três: a **rota** ainda pode dizer "seguro" onde o rover mediu terreno íngreme, o **assistente** pode citar uma fonte que não existe, e o **pacote** não roda se for copiado para outro computador.

| Gravidade     | Quantos |
| ------------- | ------- |
| 🔴 Crítico    | 5       |
| 🟠 Importante | 8       |
| 🟡 Melhoria   | 7       |

**Já corrigido hoje, durante a revisão:** o painel do ponto não diz mais "seguro" sozinho.

- **Ponto inexplorado:** sem parada do rover a menos de 100 m, aparece "Não verificado: só mapa de órbita", com alerta.
- **Selo:** passa a seguir o pior entre o mapa e o que o rover mediu. Antes ele dizia "seguro" com um PERIGO logo acima.
- **Faixa cega:** a faixa de 25 a 100 m de uma parada íngreme agora gera alerta.

## 🔴 Crítico

### 1. O trabalho de hoje não está salvo

- **O que acontece:** dezenas de arquivos do dia não estão salvos no histórico do projeto. Isso inclui o assistente, a previsão, a ficha real, a troca do modelo e as correções de segurança. A versão principal do projeto mudou depois, nos mesmos arquivos de instrução e de comandos.
- **Por que importa:** uma limpeza no lugar errado apaga o dia. E juntar tudo fica mais difícil a cada mudança nova na versão principal.
- **O que fazer:** trazer as mudanças da versão principal, resolver o conflito pequeno e salvar.

### 2. A rota diz "seguro" onde o rover mediu terreno íngreme

- **O que acontece:** o painel do ponto já foi corrigido, a rota não. Ela escolhe o caminho só pelo relevo de órbita e ignora o histórico do rover. Uma rota inteira pode sair verde sem nenhum aviso de "só órbita". Ela proíbe trechos acima de 20° no mapa, então o vermelho quase nunca aparece, mas o mapa não vê as cristas.
- **Por que importa:** a rota é o que o astronauta segue. Segurança é o primeiro critério do desafio.
- **O que fazer:** marcar na rota os trechos perto de paradas íngremes medidas pelo rover e os trechos "só órbita", com o mesmo critério do painel do ponto.

### 3. O relevo tem 6 m por pixel, não 1 m

- **O que acontece:** a fonte é de 1 m, mas foi baixada reduzida para cerca de 6 m por pixel. As cristas de 1 a 2 m somem. Das 25 paradas em que o rover mediu 15° ou mais, o mapa marca só 4, e nenhuma acima de 20°. O pior caso: o rover mediu 22,4° e o mapa diz 11°.
- **Por que importa:** é a base da inclinação no ponto e na rota. A tela ainda mostra o nome "1 m" como fonte, o que induz a erro.
- **O que fazer:** baixar de novo na resolução real (cerca de 3000×3000) e medir de novo contra as paradas do rover. Atenção: o cálculo de rota fica cerca de 36 vezes mais pesado.

### 4. O assistente inventa fonte e usa o alvo errado

- **O que acontece:** perguntado "o que é esta rocha?" em Nevado Sajama, o assistente respondeu com um alvo antigo e não com a medição CheMin real da ficha. E citou fontes que não estavam no contexto ("AI4Mars", "JPL"). Perguntado "como está a poeira hoje?", confundiu poeira com o aviso de areia.
- **Por que importa:** "nunca inventar" é a regra central do projeto e do plano. Uma fonte inventada numa demo ao vivo derruba a credibilidade de todo o resto.
- **O que fazer:** a fonte mostrada sai sempre da lista que o sistema monta, nunca do texto do modelo. Pôr a ficha real no contexto e instruir "linguagem de procedimento, nunca decide pela tripulação, diga a confiança".

### 5. O pacote offline não roda em outro computador

- **O que acontece:** as camadas do mapa guardam o endereço completo da pasta desta máquina. O pacote também está espalhado em três lugares: dados, pacote do subprojeto e modelo. Copiar para outro notebook ou outra pasta quebra o mapa. A instrução do README ("copie a pasta de dados") está errada.
- **Por que importa:** a demo pode precisar de outra máquina, e a entrega offline é a tese do produto.
- **O que fazer:** guardar os endereços relativos à pasta do projeto e testar a cópia numa pasta diferente.

## 🟠 Importante

### 6. O assistente não é de voz, não conhece a rota e é lento

- **O que acontece:**
    - A pergunta é digitada e só existe dentro do painel de um ponto. Não há microfone, e a voz existe só na saída, por botão.
    - Sem a rota no contexto, "qual a inclinação do próximo trecho?", exemplo do próprio plano, recebe "não sei".
    - Cada resposta leva cerca de 20 s, mesmo com o modelo já carregado. O modelo sai da memória após 5 min parado.
    - Se outro serviço de modelo estiver de pé na máquina, o assistente cai (os alertas continuam).
    - Condições, alertas e previsão de hoje já entram no contexto.
- **Por que importa:** é o diferencial vendido no "Durante" do plano (P1). E travar ao vivo é o risco que o próprio plano aponta.
- **O que fazer:** caixa fixa na tela, rota e ficha real no contexto, microfone com transcrição local e modelo mantido na memória.

### 7. Condições não são "da data e hora da EVA"

- **O que acontece:**
    - Não há escolha de data e hora, nem horário do Sol (nascer, pôr, altura), nem poeira esperada, nem temperatura do solo.
    - O vento não aparece e a tela não diz por quê: o sensor do rover está danificado.
    - O painel mostra a leitura do sol 4650, de 424 sols atrás, embora o sistema já tenha clima medido até o sol 4840.
    - Já existe: previsão para qualquer sol (falta só a tela) e a melhor janela do dia na rota.
- **Por que importa:** "condições" é P0 no plano e uma das três frentes do enunciado.
- **O que fazer:** campo de data e hora da EVA, horários do Sol, o dado medido mais recente e "sem dado" explícito para vento e solo.

### 8. Duas listas de alvos científicos no mesmo painel

- **O que acontece:**
    - A rota "mais ciência" conhece 3 alvos antigos, com texto de notícia. A ficha conhece 10, dos quais 6 têm medição real.
    - Cinco alvos com medição nunca entram em rota.
    - A rota passa por um alvo só, não "pelos alvos".
    - O mesmo painel pode mostrar dois alvos diferentes para o mesmo lugar.
- **Por que importa:** o plano diz que a ficha "alimenta a rota mais ciência". Hoje a rota ignora a ciência real.
- **O que fazer:** uma lista só, a da ficha, usada pela rota, pelo painel e pelo assistente.

### 9. A tela usa a lista antiga de fotos

- **O que acontece:**
    - Existem duas listas de fotos. A tela usa a antiga, que só cobre o começo da campanha. Em Nevado Sajama e no contato sul, a tela diz "nenhuma foto" e a lista nova tem 20.
    - O rótulo "9 m · S" parece dizer para onde a câmera olhava, mas é de onde a foto foi tirada. O texto "tirada a X m daqui · olhando para NE", que o plano pede, já existe e não é usado.
    - O recorte orbital do ponto existe, mas não aparece na tela.
- **Por que importa:** é a feature P0 que liga órbita e superfície, e hoje ela mostra menos do que tem.
- **O que fazer:** usar a lista nova com o rótulo certo e mostrar o recorte orbital no painel.

### 10. O plano promete coisas que o dado não sustenta

- **O que acontece:**
    - Mineralogia de órbita (CRISM): nenhuma observação na área (já conhecido).
    - Areia e terreno (AI4Mars): o conjunto de dados não cobre a época (já conhecido).
    - "Relevo de 1 m": é ~6 m (item 3).
    - "HiRISE colorido": a imagem é preto e branco, com um tom de cor cosmético.
    - Contexto regional (MOLA + HRSC): não existe.
    - Previsão: erra ±2–3 °C na mínima e ±4–5 °C na máxima, em passos de 20 sols, não "o sol seguinte". Os 0,5–1% do plano são do artigo citado, não uma meta nossa.
- **Por que importa:** a banca confere fonte. Uma promessa desmentida pelo dado derruba o resto.
- **O que fazer:** ajustar pitch e plano. Dizer o que falta e por quê, e citar o artigo como base de método.

### 11. Modo traje sem minimapa nem caminho de volta

- **O que acontece:** o modo traje esconde painéis e aumenta os alertas. O mapa e a rota continuam visíveis. Faltam minimapa, trilha de volta, pins e "voltar à base". A posição da base ainda é provisória (já conhecido).
- **Por que importa:** é a tela que o plano põe "nas mãos de quem vai usar".
- **O que fazer:** definir a base, e então montar a trilha de volta e a rota até a base no modo traje.

### 12. A rota só leva em conta distância e inclinação

- **O que acontece:**
    - Só aceita origem e destino, sem paradas no meio.
    - O caminho é escolhido só por distância e inclinação. Tempo, O₂ e dose são calculados depois, apenas para mostrar.
    - A "mais rápida" não minimiza o tempo.
    - As cristas não são favorecidas como "estrada", como o plano descreve.
    - Rocha e areia não têm dado por ponto (já conhecido).
- **Por que importa:** o plano põe radiação, tempo e O₂ no custo e promete três rotas com sentidos diferentes.
- **O que fazer:** paradas intermediárias e o tempo de verdade no custo da "mais rápida". Declarar os limites do resto.

### 13. O mapa não mostra a inclinação nem os alvos

- **O que acontece:** o plano promete uma camada de inclinação e as medições do Curiosity como pontos no mapa. Hoje a inclinação só aparece ao clicar, e os alvos científicos não aparecem no mapa.
- **Por que importa:** é a camada que o astronauta lê de relance para evitar terreno íngreme e achar ciência.
- **O que fazer:** uma camada de inclinação colorida (15° e 20°) e pins dos alvos da ficha.

## 🟡 Melhoria

### 14. Teste completo sem Wi-Fi ainda não foi feito

- **O que acontece:** a leitura do sistema não acha nenhuma chamada para fora em tempo de execução, mas o teste com a rede desligada nunca rodou. Os links "fonte" não abrem sem internet. No Chrome, a voz pode depender de rede.
- **Por que importa:** é o teste de aceitação do próprio projeto.
- **O que fazer:** rodar o teste completo sem rede e conferir as vozes instaladas na máquina da demo.

### 15. O clima de Gale vale para todos os pontos

- **O que acontece:** a previsão é a mesma para qualquer ponto. Dentro da área, o relevo varia ~720 m, o que dá ~6% de pressão (~50 Pa), mais que a faixa de erro da previsão. O plano não promete clima fora da área.
- **Por que importa:** o ajuste é física simples e melhora a previsão por ponto.
- **O que fazer:** ajustar a pressão pela altitude de cada ponto. A escala de altura de ~11 km foi conferida pela física.

### 16. Falta o botão "sincronizar" da demo

- **O que acontece:** o plano pede, na demo, um botão "sincronizar" com atraso simulado e a lista do que mudou. Não existe.
- **Por que importa:** ilustra a sincronização Terra–Marte no pitch.
- **O que fazer:** botão com atraso simulado.

### 17. Documentos discordam entre si

- **O que acontece:**
    - Feature 10: o PDF lista 9 features; o guia do projeto e o README dizem "perigos colaborativos"; o plano detalhado diz "captação de imagens de rovers".
    - O status do README está atrasado: diz que a previsão não começou e que fotos e ficha estão "a integrar".
    - O doc da F08 ainda diz "não existe rota".
    - O registro de próximos passos ainda marca o relevo como "1 m confirmado" e fala do front antigo.
- **Por que importa:** o time pode trabalhar em cima de informação velha.
- **O que fazer:** alinhar tudo com o PDF.

### 18. Testes de fotos e recorte falham

- **O que acontece:** os dois testes que cobrem fotos próximas e recorte orbital falham por falta de um pacote, e o comando de teste principal não roda os testes do subprojeto. A tela é conferida só a olho.
- **Por que importa:** um erro nessas partes chega à demo sem aviso.
- **O que fazer:** instalar o pacote faltante e pôr esses testes no comando principal.

### 19. A ficha ainda não é a "pokédex" do plano

- **O que acontece:**
    - A posição dos alvos vem da parada do rover pelo sol, não da exata (já conhecido). O Mojo tem duas paradas possíveis, e quatro alvos estão sem medição.
    - O campo "por que importa" traz o que foi feito, não a importância (água, habitabilidade).
    - Não há modal nem ícone por tipo.
    - "Argila nas cristas" não aparece nos minerais medidos.
- **Por que importa:** é o critério de contexto científico.
- **O que fazer:** fechar a posição dos alvos, reescrever "por que importa" e dar à ficha a forma do plano.

### 20. Sem vídeo de backup nem render do capacete

- **O que acontece:** o plano pede um vídeo de backup da demo e um render ou vídeo do capacete no Blender. Nenhum dos dois está no projeto.
- **Por que importa:** é o plano B contra travar ao vivo, e o visual do pitch.
- **O que fazer:** confirmar com o time quem faz cada um.

## A confirmar

- **Panorama e voz:** o panorama vem do disco e o visualizador não chama nada de fora. Falta ver o 3D num navegador real e ouvir a voz.
- **MCD e Mars-GRAM:** licença e uso offline não foram verificados. O plano também não pede clima fora da área.
- **Fontes contra a aba Resources:** a conferência de cada fonte com a aba Resources do desafio, pedida pelo plano, segue pendente.
- **Posição dos alvos de contato:** não dá para dizer se o erro é de "alguns metros".

## Próximos passos

1. Salvar o trabalho: trazer a versão principal, resolver o conflito e salvar.
2. Segurança da rota: histórico do rover e aviso "só órbita" na rota; depois, o relevo na resolução real.
3. Assistente honesto: fonte só da lista do sistema, ficha real e rota no contexto.
4. Pacote portátil: endereços relativos e teste de cópia numa pasta diferente.
5. Uma lista só de alvos e de fotos (as novas), com o rótulo "tirada a X m · olhando para".
