# Integração do F03/F04 ao projeto principal

Registro do que foi feito em 14/11/2026 e das decisões de projeto tomadas.
Commits: `b27dca6` (ficha científica com PDS, Mastcam e CRISM) e `705c18a`
(F03/F04 mesclado ao backend). O push para `origin/main` ainda não foi feito.

## 1. Sincronização com o remoto

- O `origin/main` recebeu um force-push. Os 10 commits locais antigos eram
  versões reescritas de commits que já estavam no remoto.
  - Eles ficaram guardados na branch local `backup-main-antigo`.
  - O `main` foi alinhado ao remoto com `git reset --hard origin/main`.
- O trabalho em andamento da F04 entrou em conflito com o commit `73d572f`
  (Hugo), que implementou a mesma feature de outro jeito.
  - **Decisão:** manter a versão da Victoria. Ela inclui o CRISM
    (`PublicOrbital`) e o `copy_science_files`.
  - Não entraram as funções do Hugo `localize_mastcam` (o código ficou, mas
    nada o chama), `_parada_exata`, `frase_apxs` e `frase_chemin`, nem o
    cache `.cache/pds/rdr`.
  - O teste dos helpers dele foi trocado por `test_resumo_por_regra_do_pds`.

## 2. Arquitetura atual

- **Front:** o front principal é o `web/`, em HTML/CSS/JS puro, servido pela
  API em `/`. O `frontend/` React foi removido no PR #3.
- **Execução:**
  - `make build`, uma vez e com internet, baixa e gera os dados.
  - `make run` sobe a API em http://localhost:8000.
  - O `make front` só imprime um aviso.
- **Validação do clique no mapa:**
  - O `/api/point` devolve lat/lon e `raster_values.elevacao_m`, vinda do
    DTM HiRISE 1 m.
  - A cobertura é só o recorte de teste: lon 137,3586–137,4094 e
    lat −4,8263 a −4,7757. Fora dele o valor é `null`.
- **Ollama:** fica fora por enquanto. O `make build` pula esse passo quando o
  Ollama não está instalado, e o `/api/ask` responde 503.

## 3. Decisões da integração do backend

| Tema | Decisão |
|---|---|
| Profundidade | Junção total. O código vai para `api/` e o ETL para `data-pipeline/`. Um único SQLite e um único `geo.py` |
| Fotos do rover | Fica a tabela `photos` do F03. Saem `rover_images` e os scripts `seed_rover_images.py` e `download_rover_photos.py` |
| Alvo científico | Ficam as tabelas `targets` e `measurements` do F04 (PDS real e CRISM). Saem `science_targets` e o script `seed_science_targets.py` |
| Nomes de rotas | Mantidos: `/panoramas/nearest`, `/photos/near`, `/science/card`, `/orbital/crop`, `/map` e `/bundle` |
| Dados de entrada | Movidos com `git mv` para `data-pipeline/f03/` (`dados/`, `dados_panoramas/`, `config.yaml`, `etl/`, `coletar_panoramas.py`) |
| Migração | O cache e o pacote antigos foram movidos para `data/local/f03-cache/` e `data/local/f03/`. O ETL foi regerado a partir deles, sem acessar a rede |
| Front antigo do F03 | Virou a base do `web/` (layout e estética); a pasta `web/f03/` foi removida |
| Entrega | Commits no `main` local, sem branch e sem PR. O push ainda não foi feito |

## 4. Como ficou

- **API:**
  - `api/panorama.py` (F03) e `api/ficha.py` (F04) entram como routers em
    `api/main.py`. Saiu o atalho que importava o app do subprojeto via
    `sys.path`.
  - `api/geo.py` é a única implementação de haversine, bearing, yaw e bbox,
    e o ETL também importa daqui.
- **ETL:**
  - `data-pipeline/f03/etl/build.py` monta as tabelas num arquivo temporário.
    Depois troca as tabelas do F03/F04 no `data/local/h2g2.sqlite`, numa
    transação só (`publish` em `etl/science.py`). As tabelas do time ficam
    intactas.
  - Os caminhos de saída ficam em `paths:` no `config.yaml`.
- **Contrato do `/api/point`:** chaves mantidas.
  - `nearby_photos` e `/api/photos` leem a tabela `photos`.
  - `science_target` lê `targets` e `measurements`.
  - O `mineral_crism` continua `null`. O CRISM por pixel aparece na ficha.
- **Rota "mais ciência":** usa os 10 alvos do F04
  (`vector_queries.todos_alvos_cientificos`).
- **Testes:** `api/test_f03.py` (pytest) foi incluído no `make test`, e
  `pytest>=8` entrou no `api/requirements.txt`.
- **Resultado:**
  - O ETL roda em menos de 1 s, offline, e gera 72 paradas, 73 panoramas,
    211 fotos, 10 alvos e 60 medições.
  - O `make test` passa.

## 5. Efeitos visíveis

- A camada "rastro do rover" passou de cerca de 200 fotos de 9 câmeras para
  211 fotos Navcam.
- O `/api/point` passou de 3 alvos científicos para 10.
- Quem já tem a pasta `data/local/` precisa rodar `make build` de novo.

## 6. Pendências

- Combinar com o Hugo antes do push, porque a integração remove tabelas e
  scripts que ele usava.
- Atualizar `PROXIMOS-PASSOS.md`, `docs/feature-08-agente-local.md` e
  `docs/migracao-front-html-puro.md`, que ainda citam as tabelas antigas.
- Decidir se remove a função `localize_mastcam`, que nada chama, e a pasta
  local `data/local/rover_photos/`.
- Instalar o Ollama quando o agente (`/api/ask`) for necessário.

## 7. Junção dos fronts

O `web/` usa o layout e a estética do front do subprojeto.

| Tema | Decisão |
|---|---|
| Visor | Panorama ou foto em tela cheia; cards à direita (status, panorama, fotos) e ficha F04 ao lado |
| Mapa | Uma instância MapLibre: círculo no canto inferior esquerdo, expande para tela cheia (⤢) com o seletor de camadas compacto |
| Posição atual | Rastreador simulado: `GET /api/posicao` devolve a `BASE_LAT_LON` de `api/alertas.py` (parada do sol 4650). Não há base humana em Marte |
| Rota | Origem sempre a posição atual. "Planejar rota" expande o mapa; destino por clique ou LAT/LON. Ao minimizar, o visor mostra o destino e o card de rota fica recolhido no topo |
| Card de status | Só posição (ou destino), nome IAU mais próximo e distância da parada. O resto o astronauta em rota já sabe |
| F05/F06 | Previsão, janela da EVA e medição do habitat ficam no card de rota |
| HUD | Só o nome do projeto |
| F07 modo traje | Removido |
| F08 assistente | Pílula no topo central (tecla /); responde sobre o destino ou a posição |
| Removidos | Painel do ponto, painel de condições, faixa de previsão, lightbox, `web/f03/` |
| API | `/api/posicao` novo; `alvo_cientifico` da rota ganhou `lat`/`lon` (campos novos) |
