# docs

Documentação oficial do projeto H2G2 (time DETON8 — NASA Space Apps
Salvador 2026).

- [`H2G2_Proposta_Projeto_Planejamento.md`](H2G2_Proposta_Projeto_Planejamento.md)
  — proposta de produto: features, critérios de avaliação, fontes de
  dados por feature. Documento de referência do time, não só da
  feature 01.
- [`PITCH.md`](PITCH.md) — argumento central pra apresentação: por que
  Gale (não Jezero) é o diferencial real do projeto.

- [`feature-08-agente-local.md`](feature-08-agente-local.md) — análise da feature 08 (agente
  local): dados disponíveis, alertas por regra, modo sem Terra
  (conjunção solar, radiação, poeira) e plano de implementação.
- [`feature-08-plano-implementacao.md`](feature-08-plano-implementacao.md)
  — plano de implementação da feature 08 por fase: arquivos, contratos,
  regras e casos de teste.
- [`feature-08-voz-plano-execucao.md`](feature-08-voz-plano-execucao.md) — plano de execução
  da voz: "Guia, rota até…" → Whisper → intenção → confirmação → rota no mapa → resposta falada.

- [`feature-02-sugestao-rotas-plano-execucao.md`](feature-02-sugestao-rotas-plano-execucao.md) — plano de
  execução da sugestão de rotas: todas as rotas com prós/contras, margem de volta no pior caso,
  checkpoints de O2 por voz e "voltar agora". O astronauta decide.

- [`H2G2_NasaSpaceApps_DETON8.pdf`](H2G2_NasaSpaceApps_DETON8.pdf) — plano de produto
  oficial (9 features, fontes, pesquisas de apoio).
- [`raio-x-implementacao.md`](raio-x-implementacao.md) — **o que falta**: gaps do sistema
  contra o PDF, por gravidade, com os próximos passos.
- [`feature-06-previsao-clima.md`](feature-06-previsao-clima.md) — previsão local do clima:
  método, dados, erro medido e janela de EVA.
- [`feature-06-plano-implementacao.md`](feature-06-plano-implementacao.md) — próximo passo da
  previsão: calcular quando não há dado (cascata medido → previsto → calculado), ML com
  teste contra o passado e Mars-GRAM fora de Gale.

Para o status técnico de implementação da feature 01 (mapa hiperlocal),
ver [`PROXIMOS-PASSOS.md`](../PROXIMOS-PASSOS.md) na raiz do repo.
