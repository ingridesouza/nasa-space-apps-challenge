// F02 + F06: card de rota (A* real sobre o DTM, pesos por tipo em api/route_planning.py)
// com a janela da EVA da previsão local. A origem é sempre a posição atual.
import { apagarMedicao, getPrevisao, getRoute, postMedicao } from '../api.js'
import { SLOPE_COLOR_HEX } from '../layers.js'
import { coord, esc, num } from './util.js'

const TIPO_LABEL = { mais_segura: 'Mais segura', mais_rapida: 'Mais rápida', mais_ciencia: 'Mais ciência' }
// rótulo da sugestão (api/sugestao_rotas.py): regra fixa, não o modelo
const ROTULO = { ok: ['✅', 'sem risco no mapa'], atencao: ['⚠️', 'atenção'], perigo: ['⛔', 'perigo'] }
const nomeRota = (r) => r.titulo ?? TIPO_LABEL[r.tipo] ?? r.tipo // titulo: opção do replanejamento
const VEREDITO = { ok: 'seguro', atencao: 'atencao', perigo: 'perigo' } // classes .v-* com as cores do sistema

/** F02 + F08: por que esta rota -- prós e contras com fonte; a sugerida é só a ordem, todas ficam clicáveis. */
function sugestaoHtml(r, sg) {
  const s = r.sugestao
  if (!s || !sg) return ''
  const li = (x, cls, sinal) => `<li class="${cls}" title="fonte: ${esc(x.fonte)}"><b aria-hidden="true">${sinal}</b>${esc(x.texto)}</li>`
  return `<div class="rota-sec sugestao">
    <p class="sugestao-motivo v-${VEREDITO[sg.resumo[0]?.rotulo] ?? 'atencao'}"><span class="fl-sec">Sugestão do sistema</span>${esc(sg.motivo)}</p>
    ${sg.aviso_poeira ? `<p class="sugestao-motivo v-atencao">${esc(sg.aviso_poeira)}</p>` : ''}
    <span class="fl-sec">${ROTULO[s.rotulo][0]} ${esc(nomeRota(r))}${r.tipo === sg.sugerida ? ' · sugerida ★' : ' · alternativa'}</span>
    <ul class="sugestao-lista">${s.pros.map((x) => li(x, 'pro', '+')).join('')}${s.contras.map((x) => li(x, 'contra', '!')).join('')}</ul>
    <p class="rotulo mono" title="${esc(sg.metodo)}">linha tracejada no mapa = outras opções${st.anterior ? ' e a rota anterior' : ''} · quem decide é você</p>
  </div>`
}

/** Capacidade de O2 de referência -- simulada, mesma linguagem do modelo de O2 em
 * api/route_planning.py (não é spec de traje). Editável: não há telemetria de traje. */
const RESERVA_MINIMA_PCT = 0.2
const DATA = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })
const NOME = { temp_min_c: 'mínima', temp_max_c: 'máxima', pressao_pa: 'pressão', solo_meio_dia_c: 'chão', dose_ugy_dia: 'radiação' }

const st = {
  origem: null, destino: null, escalas: [],
  data: null, erro: null, carregando: false, tipo: 'mais_segura',
  capacidade: 400,
  solEva: null, prev: undefined, prevChave: null, msgMedicao: null,
}
let el, cb
let pedido = 0
let pedidoPrev = 0

const kv = (k, v, extra = '') => `<div class="kv"${extra}><span>${k}</span><span>${v}</span></div>`

/** Mini perfil de elevação -- SVG inline, sem lib. */
function perfilSvg(perfil) {
  if (perfil.length < 2) return ''
  const w = 300, h = 48
  const elev = perfil.map((p) => p.elevacao_m)
  const distMax = perfil.at(-1).distancia_acumulada_m || 1
  const min = Math.min(...elev)
  const faixa = Math.max(...elev) - min || 1
  const pts = perfil.map((p) => `${((p.distancia_acumulada_m / distMax) * w).toFixed(1)},${(h - ((p.elevacao_m - min) / faixa) * h).toFixed(1)}`).join(' ')
  return `<svg class="perfil" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Perfil de elevação: ${num(min, 0)} a ${num(min + faixa, 0)} m">
    <polyline points="${pts}" fill="none" stroke="var(--b300)" stroke-width="1.5" vector-effect="non-scaling-stroke"/></svg>`
}

/** Curva do dia (SVG inline) com a janela de EVA em destaque. */
function curvaSvg(janela) {
  const pts = Object.entries(janela?.curva_por_hora ?? {}).map(([h, t]) => [Number(h), t]).sort((a, b) => a[0] - b[0])
  if (pts.length < 2) return '<p class="rotulo mono">sem curva por hora para este sol</p>'
  const W = 300, H = 64, P = 4
  const ts = pts.map((p) => p[1])
  const [tmin, tmax] = [Math.min(...ts), Math.max(...ts)]
  const x = (h) => P + (h / 23) * (W - 2 * P)
  const y = (t) => P + (1 - (t - tmin) / (tmax - tmin || 1)) * (H - 2 * P - 10)
  const ini = Number(janela.inicio_lmst.slice(0, 2))
  const fim = ini + janela.horas
  const linha = pts.map(([h, t], i) => `${i ? 'L' : 'M'}${x(h).toFixed(1)},${y(t).toFixed(1)}`).join(' ')
  return `<svg class="curva" viewBox="0 0 ${W} ${H}" role="img"
      aria-label="Temperatura prevista por hora: de ${num(tmin, 0)} a ${num(tmax, 0)} °C; melhor janela ${esc(janela.inicio_lmst)}–${esc(janela.fim_lmst)}">
    <rect x="${x(ini)}" y="0" width="${Math.max(x(Math.min(fim, 23)) - x(ini), 3)}" height="${H - 10}" class="curva-janela"/>
    <path d="${linha}" class="curva-linha"/>
    ${[0, 6, 12, 18].map((h) => `<text x="${x(h)}" y="${H - 1}" class="curva-eixo">${h}h</text>`).join('')}
    <text x="${W - P}" y="${y(tmax) + 3}" class="curva-eixo" text-anchor="end">${num(tmax, 0)}°</text>
    <text x="${W - P}" y="${y(tmin)}" class="curva-eixo" text-anchor="end">${num(tmin, 0)}°</text>
  </svg>`
}

/** O₂ numa barra só: ida e ida + volta (mesmo custo: o modelo de velocidade só
 * depende da magnitude da inclinação, não da direção). */
function o2Html(r) {
  const cap = st.capacidade
  const limite = (1 - RESERVA_MINIMA_PCT) * cap
  const pct = (l) => Math.min(100, (l / cap) * 100)
  const ida = r.o2_estimado_l, volta = r.o2_estimado_l * 2
  const cor = (l) => (l <= limite ? 'var(--ok)' : 'var(--mars2)')
  return `<div class="rota-sec">
    <div class="fl-top"><span class="fl-sec">O₂ estimado · simulado</span>
      <label class="o2-cap mono">traje <input type="number" min="1" step="1" value="${cap}" data-campo="capacidade-o2" aria-label="Capacidade de O₂ do traje em litros"> L</label></div>
    <div class="o2" role="img" aria-label="Ida ${num(ida, 1)} L, ida e volta ${num(volta, 1)} L de ${cap} L">
      <div class="o2-volta" style="width:${pct(volta)}%;background:${cor(volta)}"></div>
      <div class="o2-ida" style="width:${pct(ida)}%;background:${cor(ida)}"></div>
      <div class="o2-reserva" style="left:${100 - RESERVA_MINIMA_PCT * 100}%" title="reserva mínima de 20%"></div>
    </div>
  </div>`
}

function detalheRota(r, topo = '') {
  const alvo = r.alvo_cientifico
  return `${o2Html(r)}
    ${topo}
    ${alvo ? `<div class="rota-sec"><span class="fl-sec">Passa perto de</span>
      <button type="button" class="alvo-btn" data-acao="alvo">◇ ${esc(alvo.nome)} <span class="mono">abrir ficha ›</span></button></div>` : ''}`
}

/** F06: "acoplar a previsão à rota, sugerindo a melhor janela para a EVA". */
function carregarPrev(chave, minutos) {
  const meu = ++pedidoPrev
  st.prevChave = chave
  st.prev = undefined
  getPrevisao({ duracao_min: minutos, ...(st.solEva && { sol: st.solEva }) })
    .catch(() => null)
    .then((p) => {
      if (meu !== pedidoPrev) return
      st.prev = p
      render()
    })
}

function formMedicao(p) {
  const local = p?.medicao_local
  return `<details class="medir"${st.msgMedicao ? ' open' : ''}>
    <summary class="mono">＋ medição do habitat</summary>
    <form data-medir>
      <label>sol <input name="sol" type="number" min="1" step="1" required value="${esc(local?.sol ?? p?.sol ?? '')}"></label>
      <label>mín °C <input name="temp_min_c" type="number" step="0.1" required></label>
      <label>máx °C <input name="temp_max_c" type="number" step="0.1" required></label>
      <label>Pa <input name="pressao_pa" type="number" step="0.1" required></label>
      <label>µGy/dia <input name="dose_ugy_dia" type="number" step="1" placeholder="opcional"></label>
      <button class="btn btn-sm">salvar</button>
      ${local ? `<button type="button" class="link-btn" data-apagar-medicao="${esc(local.sol)}">apagar medição do sol ${esc(local.sol)}</button>` : ''}
    </form>
    ${st.msgMedicao ? `<p class="rotulo mono" role="status">${esc(st.msgMedicao)}</p>` : ''}
  </details>`
}

function secaoEva(r) {
  const minutos = r.tempo_estimado_min
  const chave = `${st.solEva}|${minutos}`
  if (st.prevChave !== chave) carregarPrev(chave, minutos)
  const p = st.prev
  const sol = st.solEva ?? p?.sol ?? ''
  const topo = `<div class="fl-top"><span class="fl-sec">Janela da EVA · ${esc(Math.ceil(minutos / 60))}h</span>
    <span class="sol-passo mono">
      <button type="button" data-sol-passo="-1" aria-label="Sol anterior">‹</button>
      <label>sol <input type="number" data-sol-eva min="1" step="1" value="${esc(sol)}" aria-label="Sol da EVA"></label>
      <button type="button" data-sol-passo="1" aria-label="Próximo sol">›</button>
    </span></div>`
  let corpo
  if (p === undefined) corpo = '<p class="vazio">calculando pela previsão local…</p>'
  else if (p === null) corpo = '<p class="vazio erro">Falha ao consultar a previsão.</p>'
  else if (!p.temp_min_c || !p.temp_max_c) corpo = `<p class="vazio">Sem previsão para o sol ${esc(p.sol)}: nenhum ano anterior medido nessa estação.</p>`
  else {
    const j = p.janela_eva
    const doseEva = p.dose_ugy_dia ? (p.dose_ugy_dia.valor / 24) * (minutos / 60) : null
    const erro = p.erro_backtest
    const div = p.divergencia?.length
      ? `<p class="rotulo mono aviso" role="alert">⚠ Medição do sol ${esc(p.medicao_local.sol)} fora do normal da estação (${p.divergencia.map((d) => `${NOME[d.campo] ?? esc(d.campo)} ${num(d.medido, 0)} medido × ${num(d.esperado, 0)} esperado`).join(' · ')}). A previsão vale menos até o tempo voltar ao padrão.</p>`
      : ''
    corpo = `${j ? `<p class="eva-hora">${esc(j.inicio_lmst)}–${esc(j.fim_lmst)} <small class="mono">hora solar local · pior hora ${num(j.temp_mais_fria_na_janela_c, 0)} °C</small></p>` : '<p class="vazio">sem curva horária para prever a janela</p>'}
      ${curvaSvg(j)}
      ${kv('Ar', `${num(p.temp_min_c.valor, 0)}° a ${num(p.temp_max_c.valor, 0)} °C`)}
      ${p.solo_meio_dia_c ? kv('Chão 12h', `~${num(p.solo_meio_dia_c.valor, 0)} °C`) : ''}
      ${p.pressao_pa ? kv('Pressão', `${num(p.pressao_pa.valor, 0)} Pa`) : ''}
      ${p.dose_ugy_dia ? kv('Radiação', `${num(p.dose_ugy_dia.valor, 0)} µGy/dia`) : ''}
      ${doseEva !== null ? kv('Dose nesta EVA', `~${num(doseEva, 1)} µGy`) : ''}
      ${div}
      <p class="rotulo mono" title="${esc(p.metodo)} · ${esc(p.fonte)}">${p.data_terra ? `${esc(DATA.format(new Date(`${p.data_terra}T12:00:00Z`)))} na Terra · Ls ${num(p.ls, 0)}° · ` : ''}estimado, não medido · erro típico ±${num(erro?.temp_min_c?.erro_medio, 1)} °C (mín.)${erro?.dose_ugy_dia ? ` · ±${num(erro.dose_ugy_dia.erro_medio, 0)} µGy/dia` : ''} · base: ${p.base_origem === 'local' ? `medição do habitat, sol ${esc(p.sol_base)}` : `PDS, sol ${esc(p.sol_base)}`}</p>`
  }
  return `<div class="rota-sec">${topo}${corpo}${p ? formMedicao(p) : ''}</div>`
}

const rotaAtiva = () => st.data?.rotas.find((r) => r.tipo === st.tipo) ?? null
// as outras opções e, depois de um replanejamento, a rota que estava sendo seguida: tudo tracejado no mapa
const outrasRotas = () => [...(st.data?.rotas.filter((r) => r.tipo !== st.tipo) ?? []), ...(st.anterior ? [st.anterior] : [])]
const fimDa = (r) => ({ lat: r.pontos.at(-1)[0], lon: r.pontos.at(-1)[1] })

/** F02 + F08: opções do /api/replanejar (problema relatado no meio da caminhada). Mesmo card das
 * variantes; a rota que estava aberta continua tracejada no mapa. Nada é escolhido sozinho. */
export function mostrarOpcoes(res, origem) {
  const anterior = st.anterior ?? rotaAtiva()
  pedido++ // descarta um cálculo de rota em andamento
  const sugerida = res.rotas.find((r) => r.tipo === res.sugestao.sugerida) ?? res.rotas[0]
  Object.assign(st, { origem, destino: fimDa(sugerida), escalas: [], data: res, erro: null, carregando: false, tipo: sugerida.tipo, anterior })
  render()
  cb.onRotaAtiva(rotaAtiva(), outrasRotas())
}

/** F08: a rota aberta, no formato que /api/ask espera; null sem rota calculada. */
export function rotaParaAgente() {
  const { origem: o, destino: d } = st
  if (!rotaAtiva() || !o || !d) return null
  return { origin_lat: o.lat, origin_lon: o.lon, dest_lat: d.lat, dest_lon: d.lon, tipo: st.tipo, ...(st.solEva && { sol: st.solEva }) }
}

function render() {
  let corpo
  // legenda das cores do traçado (mesmas faixas de api/route_planning.py)
  const legenda = st.data ? `<div class="legenda-rota mono"><span class="legenda-titulo">Inclinação</span><div>${[['seguro', '< 15°'], ['atencao', '15–20°'], ['perigo', '≥ 20°']]
    .map(([k, t]) => `<span><i style="background:${SLOPE_COLOR_HEX[k]}"></i>${t}</span>`).join('')}</div></div>` : ''
  const topo = st.destino ? `<div class="rota-sec rota-topo">${legenda}<span><button type="button" class="link-btn" data-acao="marcar-posicao" title="sem GPS: clique no mapa onde você está; replanejar parte daí">📍 estou aqui</button> <button type="button" class="link-btn" data-acao="adicionar-escala">+ parada no caminho</button></span></div>` : ''
  if (!st.destino) corpo = '<p class="vazio">Clique no mapa ou digite as coordenadas do destino.</p>'
  else {
    corpo = `<div class="rota-sec">
      ${st.escalas.map((p, i) => kv(`Parada ${i + 1}`, `${coord(p)} <button type="button" class="link-btn" data-acao="remover-escala" data-i="${i}" aria-label="Remover parada ${i + 1}">×</button>`)).join('')}
      ${kv('Destino', coord(st.destino))}
      ${rotaAtiva() ? kv('Comprimento da rota', `${num(rotaAtiva().distancia_m)} m`) + kv('Tempo · ida + volta', `~${num(rotaAtiva().tempo_estimado_min * 2)} min`) : ''}
    </div>`
    if (st.carregando) corpo += '<p class="vazio">calculando rota (A* sobre o DTM)…</p>'
    if (st.erro) corpo += `<p class="vazio erro">${esc(st.erro)}</p>`
    if (st.data) {
      corpo += `<div class="tipos">${st.data.rotas
        .map((r) => {
          const [ico, txt] = ROTULO[r.sugestao?.rotulo] ?? ['', '']
          return `<button type="button" class="tipo ${r.tipo === st.tipo ? 'on' : ''}" data-tipo="${r.tipo}" aria-label="${esc(nomeRota(r))}: ${txt}">${ico} ${esc(nomeRota(r))}${r.tipo === st.data.sugestao?.sugerida ? ' ★' : ''}<small class="tipo-meta">${num(r.distancia_m, 0)} m · ${num(r.tempo_estimado_min, 0)} min</small></button>`
        }).join('')}</div>`
      const r = rotaAtiva()
      if (st.data.problema_texto) {
        corpo = `<div class="rota-sec"><p class="sugestao-motivo v-perigo"><span class="fl-sec">Problema relatado · novas opções</span>${esc(st.data.problema_texto)}</p></div>` + corpo
      }
      if (r) corpo += sugestaoHtml(r, st.data.sugestao) + detalheRota(r, topo)
    }
    if (!rotaAtiva()) corpo += topo // sem rota calculada ainda: o botão de parada já fica à mão
  }
  el.innerHTML = `<div class="rota-corpo">
    <div class="rota-body">${corpo}
      <button type="button" class="link-btn rota-cancelar" data-acao="cancelar">✕ cancelar rota</button></div>
  </div>`
}

/** callbacks: onCancelar(), onRotaAtiva(rota|null, outras[]), onAdicionarEscala(), onMarcarPosicao(), onRemoverEscala(i), onAbrirAlvo(alvo). */
export function iniciarRota(container, callbacks) {
  el = container
  cb = callbacks
  el.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-acao],[data-tipo],[data-sol-passo],[data-apagar-medicao]')
    if (!b) return
    if (b.dataset.tipo) {
      st.tipo = b.dataset.tipo
      if (st.data?.problema) st.destino = fimDa(rotaAtiva()) // opção de volta termina na base, não no destino
      cb.onRotaAtiva(rotaAtiva(), outrasRotas())
    } else if (b.dataset.solPasso) {
      const base = st.solEva ?? st.prev?.sol
      if (base) st.solEva = Math.max(1, base + Number(b.dataset.solPasso))
    } else if (b.dataset.apagarMedicao) {
      await apagarMedicao(b.dataset.apagarMedicao)
      st.msgMedicao = `medição do sol ${b.dataset.apagarMedicao} apagada`
      st.prevChave = null
    } else {
      const a = b.dataset.acao
      if (a === 'cancelar') return cb.onCancelar()
      if (a === 'adicionar-escala') return cb.onAdicionarEscala()
      if (a === 'marcar-posicao') return cb.onMarcarPosicao()
      if (a === 'remover-escala') return cb.onRemoverEscala(Number(b.dataset.i))
      if (a === 'alvo') return cb.onAbrirAlvo(rotaAtiva()?.alvo_cientifico)
    }
    render()
  })
  el.addEventListener('toggle', (e) => {
  }, true)
  // 'change' (não 'input'): render() troca o innerHTML e derrubaria o foco a cada tecla
  el.addEventListener('change', (e) => {
    const v = Number(e.target.value)
    if (e.target.dataset.campo === 'capacidade-o2' && v > 0) st.capacidade = v
    else if (e.target.matches('[data-sol-eva]') && Number.isInteger(v) && v >= 1) st.solEva = v
    else return
    render()
  })
  // medição do habitat: vira a base da previsão, sem a Terra
  el.addEventListener('submit', async (e) => {
    if (!e.target.matches('[data-medir]')) return
    e.preventDefault()
    const dados = Object.fromEntries([...new FormData(e.target)].filter(([, v]) => v !== '').map(([k, v]) => [k, Number(v)]))
    try {
      const m = await postMedicao(dados)
      st.msgMedicao = `medição do sol ${m.sol} salva: as previsões seguintes partem dela`
    } catch (err) {
      st.msgMedicao = err.message
    }
    st.prevChave = null
    render()
  })
  return async function atualizarRota(origem, destino, escalas = []) {
    Object.assign(st, { origem, destino, escalas, data: null, erro: null, carregando: Boolean(origem && destino), anterior: null })
    const meu = ++pedido
    cb.onRotaAtiva(null)
    render()
    if (!st.carregando) return
    try {
      const data = await getRoute(origem, destino, escalas)
      if (meu !== pedido) return // pontos mudaram no meio do cálculo
      st.data = data
      st.tipo = data.sugestao?.sugerida ?? 'mais_segura'
    } catch (e) {
      if (meu !== pedido) return
      st.erro = e.message
    }
    st.carregando = false
    cb.onRotaAtiva(rotaAtiva(), outrasRotas())
    render()
    return st.data // F08 voz: o resumo falado sai destes números
  }
}
