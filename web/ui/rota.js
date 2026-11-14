// Feature 02: painel de rota (antes RoutePanel.tsx). Mesmo A* real sobre o DTM,
// pesos diferentes por tipo (ver api/route_planning.py).
import { getPrevisao, getRoute } from '../api.js'
import { coord, esc, num, veredito } from './util.js'

const TIPO_LABEL = { mais_segura: 'Mais segura', mais_rapida: 'Mais rápida', mais_ciencia: 'Mais ciência' }

/** Capacidade de O2 de referência pra barra -- simulada, mesma linguagem
 * do modelo de O2/tempo em api/route_planning.py (não é spec de traje). */
const CAPACIDADE_O2_L_SIMULADA = 400
const RESERVA_MINIMA_PCT = 0.2

function piorStatus(rota) {
  if (rota.trechos_risco.some((t) => t.slope_status === 'perigo')) return 'perigo'
  if (rota.trechos_risco.some((t) => t.slope_status === 'atencao')) return 'atencao'
  return 'seguro'
}

/** Mini perfil de elevação -- SVG inline, sem lib. */
function perfilSvg(perfil) {
  if (perfil.length < 2) return ''
  const w = 260
  const h = 56
  const elev = perfil.map((p) => p.elevacao_m)
  const distMax = perfil.at(-1).distancia_acumulada_m || 1
  const min = Math.min(...elev)
  const faixa = Math.max(...elev) - min || 1
  const pts = perfil.map((p) => `${((p.distancia_acumulada_m / distMax) * w).toFixed(1)},${(h - ((p.elevacao_m - min) / faixa) * h).toFixed(1)}`).join(' ')
  return `<svg width="${w}" height="${h}" style="display:block"><polyline points="${pts}" fill="none" stroke="var(--hud-cyan)" stroke-width="1.5"/></svg>`
}

function detalheRota(r) {
  const status = piorStatus(r)
  const o2Pct = (r.o2_estimado_l / CAPACIDADE_O2_L_SIMULADA) * 100
  const o2Ok = o2Pct <= (1 - RESERVA_MINIMA_PCT) * 100
  const alvo = r.alvo_cientifico

  // Ida e volta: nosso modelo de velocidade só depende da magnitude da
  // inclinação do trecho (ver api/route_planning.py, custo_aresta), não
  // da direção -- subida e descida custam o mesmo no modelo. Então o
  // caminho de volta (mesma rota, sentido invertido) tem o MESMO custo
  // da ida, não é uma suposição otimista, é consequência direta do
  // modelo já existente. Dobrar é honesto aqui -- ver aviso na UI.
  const o2VoltaL = r.o2_estimado_l * 2
  const o2VoltaPct = (o2VoltaL / CAPACIDADE_O2_L_SIMULADA) * 100
  const voltaOk = o2VoltaPct <= (1 - RESERVA_MINIMA_PCT) * 100
  const doseVolta = r.dose_rad_estimada_ugy !== null ? r.dose_rad_estimada_ugy * 2 : null

  return `<div style="margin-bottom:var(--s-3)">
    ${veredito(status, [
      { ok: status !== 'perigo', label: 'Nenhum trecho acima do limite de 20°' },
      { ok: o2Ok, label: 'O₂ dentro da reserva simulada (20%) só pra ida' },
      { ok: voltaOk, label: 'O₂ também alcança pra voltar (ida + volta)' },
    ])}
    <div class="h2g2-card h2g2-stat-grid" style="margin-top:var(--s-2)">
      <div><span class="h2g2-stat-label">Distância (ida)</span><span class="h2g2-stat-value">${num(r.distancia_m)}m</span></div>
      <div><span class="h2g2-stat-label">Tempo (ida)</span><span class="h2g2-stat-value">~${num(r.tempo_estimado_min)} min</span></div>
      <div class="h2g2-full">
        <span class="h2g2-stat-label">O₂ estimado (simulado, só ida)</span>
        <span class="h2g2-stat-value">${num(r.o2_estimado_l, 1)}L de ${CAPACIDADE_O2_L_SIMULADA}L</span>
        <div class="h2g2-progress" style="margin-top:4px">
          <div class="h2g2-progress-fill" style="width:${Math.min(o2Pct, 100)}%;background:${o2Ok ? 'var(--verdict-seguro)' : 'var(--verdict-perigo)'}"></div>
        </div>
      </div>
      <div class="h2g2-full">
        <span class="h2g2-stat-label">Dose de radiação (RAD, real, só ida)</span>
        <span class="h2g2-stat-value">${r.dose_rad_estimada_ugy !== null ? `${r.dose_rad_estimada_ugy.toFixed(2)} µGy` : '—'}</span>
      </div>
    </div>
    <div class="h2g2-card" style="margin-top:var(--s-2)">
      <span class="h2g2-stat-label">Ida + volta (mesma rota, sentido inverso)</span>
      <span class="h2g2-stat-value">${num(r.o2_estimado_l * 2, 1)}L de ${CAPACIDADE_O2_L_SIMULADA}L</span>
      <div class="h2g2-progress" style="margin-top:4px">
        <div class="h2g2-progress-fill" style="width:${Math.min(o2VoltaPct, 100)}%;background:${voltaOk ? 'var(--verdict-seguro)' : 'var(--verdict-perigo)'}"></div>
      </div>
      <div class="h2g2-dim h2g2-micro" style="margin-top:4px;line-height:1.4">
        ~${num(r.tempo_estimado_min * 2)} min · ${doseVolta !== null ? `${doseVolta.toFixed(2)} µGy` : '—'} de radiação no total.
        Assume o mesmo custo da ida (nosso modelo de velocidade não diferencia subida de descida).
      </div>
    </div>
    <div class="h2g2-card" style="margin-top:var(--s-2)"><span class="h2g2-stat-label">Perfil de elevação</span>${perfilSvg(r.perfil_elevacao)}</div>
    ${alvo ? `<div class="h2g2-card" style="margin-top:var(--s-2)">
        <span class="h2g2-stat-label">Passa perto de</span>
        <div class="h2g2-display h2g2-small" style="color:var(--ink);margin-bottom:4px">${esc(alvo.nome)}</div>
        ${alvo.medicao_curiosity ? `<div class="h2g2-dim h2g2-micro" style="line-height:1.4">${esc(alvo.medicao_curiosity)}</div>` : ''}
      </div>` : ''}
  </div>`
}

// estado do painel: resposta da API, tipo escolhido, aviso de areia expandido.
// O aviso é genérico da região -- cheio na primeira vez da sessão, depois só um link.
let data = null
let tipo = 'mais_segura'
let avisoExpandido = true
let erro = null
let carregando = false
let pedido = 0
let el, cb
let ultimo = { origem: null, destino: null }
const janelas = new Map() // tempo_estimado_min -> janela_eva (F06); undefined = calculando

/** F06 no PDF: "acoplar a previsão à rota, sugerindo a melhor janela para a EVA". */
function secaoJanela(r) {
  const chave = r.tempo_estimado_min
  if (!janelas.has(chave)) {
    janelas.set(chave, undefined)
    getPrevisao({ duracao_min: chave })
      .then((p) => p.janela_eva, () => null)
      .then((j) => {
        janelas.set(chave, j)
        render(ultimo.origem, ultimo.destino)
      })
  }
  const j = janelas.get(chave)
  const corpo = j === undefined
    ? '<span class="h2g2-dim">calculando pela previsão local...</span>'
    : j === null
      ? '<span class="h2g2-dim">sem curva horária para prever a janela</span>'
      : `<strong>${esc(j.inicio_lmst)}–${esc(j.fim_lmst)}</strong> hora solar local · hora mais fria prevista ${num(j.temp_mais_fria_na_janela_c, 0)} °C
         <div class="h2g2-dim h2g2-micro" title="${esc(j.criterio)}">estimado (não medido) · climatologia REMS por hora</div>`
  return `<div class="h2g2-small h2g2-sep" style="margin-bottom:var(--s-3)"><span class="h2g2-stat-label">Melhor janela p/ esta EVA (${esc(Math.ceil(chave / 60))}h)</span><div>${corpo}</div></div>`
}

const rotaAtiva = () => data?.rotas.find((r) => r.tipo === tipo) ?? null

function render(origem, destino) {
  let corpo
  if (!origem) corpo = '<div class="h2g2-dim h2g2-mono h2g2-small">Clique no mapa pra marcar a origem.</div>'
  else if (!destino) corpo = `<div class="h2g2-dim h2g2-mono h2g2-small">Origem: ${coord(origem)}<br>Clique no mapa pra marcar o destino.</div>`
  else {
    corpo = `<button class="h2g2-link-btn" data-acao="reset" style="margin-bottom:var(--s-3)">↺ escolher outros pontos</button>`
    if (carregando) corpo += '<div class="h2g2-dim h2g2-mono h2g2-small">calculando rota (A* sobre o DTM)...</div>'
    if (erro) corpo += `<div class="h2g2-erro">${esc(erro)}</div>`
    if (data) {
      corpo += `<div class="h2g2-tipos">${data.rotas
        .map((r) => `<button class="h2g2-tipo ${r.tipo === tipo ? 'on' : ''}" data-tipo="${r.tipo}">${TIPO_LABEL[r.tipo] ?? esc(r.tipo)}</button>`)
        .join('')}</div>`
      const r = rotaAtiva()
      if (r) corpo += detalheRota(r) + secaoJanela(r)
      if (data.avisos.length > 0) {
        corpo += avisoExpandido
          ? `<div>
              <div class="h2g2-linha-topo">
                <p class="h2g2-panel-title">Avisos gerais da região</p>
                <button class="h2g2-close-btn h2g2-small" data-acao="recolher" aria-label="Entendi, recolher avisos">×</button>
              </div>
              ${data.avisos.map((a) => `<div class="h2g2-mono h2g2-aviso">⚠ ${esc(a)}</div>`).join('')}
            </div>`
          : '<button class="h2g2-link-btn" data-acao="expandir">⚠ ver avisos gerais da região</button>'
      }
    }
  }
  el.innerHTML = `<div class="h2g2-linha-topo">
      <p class="h2g2-panel-title">Planejar rota</p>
      <button class="h2g2-close-btn" data-acao="fechar" aria-label="Fechar">×</button>
    </div>${corpo}`
}

/** Liga o painel. callbacks: onFechar(), onReset(), onRotaAtiva(rota|null). */
export function iniciarRota(container, callbacks) {
  el = container
  cb = callbacks
  el.addEventListener('click', (e) => {
    const b = e.target.closest('[data-acao],[data-tipo]')
    if (!b) return
    if (b.dataset.tipo) {
      tipo = b.dataset.tipo
      cb.onRotaAtiva(rotaAtiva())
    } else if (b.dataset.acao === 'fechar') return cb.onFechar()
    else if (b.dataset.acao === 'reset') return cb.onReset()
    else avisoExpandido = b.dataset.acao === 'expandir'
    render(ultimo.origem, ultimo.destino)
  })
  return async function atualizarRota(origem, destino) {
    ultimo = { origem, destino }
    const meu = ++pedido
    data = null
    erro = null
    carregando = Boolean(origem && destino)
    cb.onRotaAtiva(null)
    render(origem, destino)
    if (!carregando) return
    try {
      data = await getRoute(origem, destino)
      tipo = 'mais_segura'
    } catch (e) {
      erro = e.message
    }
    if (meu !== pedido) return // pontos mudaram no meio do cálculo
    carregando = false
    cb.onRotaAtiva(rotaAtiva())
    render(origem, destino)
  }
}
