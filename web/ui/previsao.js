// Feature 06: faixa de previsão (sol da EVA, números do dia, curva por hora com a
// melhor janela). Só desenha; app.js busca /api/previsao e trata ‹ › e o campo do sol.
import { esc, num } from './util.js'

const DATA = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })
const dataTerra = (iso) => (iso ? DATA.format(new Date(`${iso}T12:00:00Z`)) : '')

/** Curva do dia (SVG inline, sem lib) com a janela de EVA em destaque. */
function curvaSvg(janela) {
  const pts = Object.entries(janela?.curva_por_hora ?? {}).map(([h, t]) => [Number(h), t]).sort((a, b) => a[0] - b[0])
  if (pts.length < 2) return '<div class="h2g2-dim h2g2-micro">sem curva por hora para este sol</div>'
  const W = 260, H = 64, P = 4
  const ts = pts.map((p) => p[1])
  const [tmin, tmax] = [Math.min(...ts), Math.max(...ts)]
  const x = (h) => P + (h / 23) * (W - 2 * P)
  const y = (t) => P + (1 - (t - tmin) / (tmax - tmin || 1)) * (H - 2 * P - 10)
  const ini = Number(janela.inicio_lmst.slice(0, 2))
  const fim = ini + janela.horas
  const linha = pts.map(([h, t], i) => `${i ? 'L' : 'M'}${x(h).toFixed(1)},${y(t).toFixed(1)}`).join(' ')
  return `<svg class="h2g2-curva" viewBox="0 0 ${W} ${H}" role="img"
      aria-label="Temperatura prevista por hora: de ${num(tmin, 0)} a ${num(tmax, 0)} °C; melhor janela ${esc(janela.inicio_lmst)}–${esc(janela.fim_lmst)}">
    <rect x="${x(ini)}" y="0" width="${Math.max(x(Math.min(fim, 23)) - x(ini), 3)}" height="${H - 10}" class="h2g2-curva-janela"/>
    <path d="${linha}" class="h2g2-curva-linha"/>
    ${[0, 6, 12, 18].map((h) => `<text x="${x(h)}" y="${H - 1}" class="h2g2-curva-eixo">${h}h</text>`).join('')}
    <text x="${W - P}" y="${y(tmax) + 3}" class="h2g2-curva-eixo" text-anchor="end">${num(tmax, 0)}°</text>
    <text x="${W - P}" y="${y(tmin)}" class="h2g2-curva-eixo" text-anchor="end">${num(tmin, 0)}°</text>
  </svg>`
}

const NOME = { temp_min_c: 'mínima', temp_max_c: 'máxima', pressao_pa: 'pressão', solo_meio_dia_c: 'chão', dose_ugy_dia: 'radiação' }

/** Aviso quando a medição local foge do normal da estação: algo mudou (frente, poeira). */
function avisoDivergencia(p) {
  if (!p.divergencia?.length) return ''
  const itens = p.divergencia.map((d) => `${NOME[d.campo] ?? esc(d.campo)} ${num(d.medido, 0)} medido × ${num(d.esperado, 0)} esperado`).join(' · ')
  return `<div class="h2g2-prev-alerta" role="alert">● Medição do sol ${esc(p.medicao_local.sol)} fora do normal da estação (${itens}). A previsão vale menos até o tempo voltar ao padrão.</div>`
}

/** Formulário da medição local (sensor do habitat/traje). */
function formMedicao(p, msg) {
  const local = p?.medicao_local
  return `<details class="h2g2-prev-medir"${msg ? ' open' : ''}>
    <summary>＋ medição do habitat</summary>
    <form data-medir>
      <label>sol <input name="sol" type="number" min="1" step="1" required value="${esc(local?.sol ?? p?.sol ?? '')}"></label>
      <label>mín °C <input name="temp_min_c" type="number" step="0.1" required></label>
      <label>máx °C <input name="temp_max_c" type="number" step="0.1" required></label>
      <label>Pa <input name="pressao_pa" type="number" step="0.1" required></label>
      <label>µGy/dia <input name="dose_ugy_dia" type="number" step="1" placeholder="opcional"></label>
      <button class="h2g2-mono">salvar</button>
      ${local ? `<button type="button" class="h2g2-link-btn" data-apagar-medicao="${esc(local.sol)}">apagar medição do sol ${esc(local.sol)}</button>` : ''}
    </form>
    ${msg ? `<div class="h2g2-micro" role="status">${esc(msg)}</div>` : ''}
  </details>`
}

const bloco = (rotulo, valor, unidade, extra = '') =>
  `<div class="h2g2-prev-num"><span class="h2g2-stat-label">${rotulo}</span><span class="h2g2-prev-valor"${extra}>${valor}<small>${unidade}</small></span></div>`

/** el: #previsao. estado: { previsao, validacao, solEva, carregando } */
export function renderPrevisao(el, { previsao: p, validacao: v, solEva, carregando, msgMedicao }) {
  const sol = p?.sol ?? solEva
  if (!sol) {
    el.innerHTML = '<div class="h2g2-dim h2g2-mono h2g2-small">previsão: carregando...</div>'
    return
  }
  const seletor = `<div class="h2g2-prev-sol">
      <p class="h2g2-panel-title">Previsão local</p>
      <div class="h2g2-prev-passo">
        <button type="button" data-sol-passo="-1" aria-label="Sol anterior">‹</button>
        <label>sol <input type="number" data-sol-eva min="1" step="1" value="${esc(sol)}" aria-label="Sol da EVA"></label>
        <button type="button" data-sol-passo="1" aria-label="Próximo sol">›</button>
      </div>
      <div class="h2g2-dim h2g2-micro">${p ? `${esc(dataTerra(p.data_terra))} na Terra · Ls ${num(p.ls, 0)}°` : ''}${carregando ? ' · calculando...' : ''}</div>
    </div>`
  if (!p?.temp_min_c || !p?.temp_max_c) {
    el.innerHTML = `${seletor}<div class="h2g2-dim h2g2-small">Sem previsão para o sol ${esc(sol)}: nenhum ano anterior medido nessa estação.</div>`
    return
  }
  const erro = p.erro_backtest
  const j = p.janela_eva
  const teste = v?.medido && v.temp_min_c
    ? ` · teste sol ${esc(v.sol)}: previsto ${num(v.temp_min_c.valor, 0)}°/${num(v.temp_max_c.valor, 0)}° × medido ${num(v.medido.temp_min_c, 0)}°/${num(v.medido.temp_max_c, 0)}°`
    : ''
  el.innerHTML = `${seletor}
    <div class="h2g2-prev-nums">
      ${bloco('Ar', `${num(p.temp_min_c.valor, 0)}° a ${num(p.temp_max_c.valor, 0)}`, '°C')}
      ${p.solo_meio_dia_c ? bloco('Chão 12h', `~${num(p.solo_meio_dia_c.valor, 0)}`, '°C') : ''}
      ${p.pressao_pa ? bloco('Pressão', num(p.pressao_pa.valor, 0), 'Pa') : ''}
      ${p.dose_ugy_dia ? bloco('Radiação', num(p.dose_ugy_dia.valor, 0), 'µGy/dia', ' style="color:var(--ember)"') : ''}
    </div>
    <div class="h2g2-prev-janela">
      <span class="h2g2-stat-label">Melhor janela p/ EVA de ${esc(j?.horas ?? 2)}h</span>
      ${j ? `<div class="h2g2-prev-hora">${esc(j.inicio_lmst)}–${esc(j.fim_lmst)} <small>hora local · pior hora ${num(j.temp_mais_fria_na_janela_c, 0)}°C</small></div>` : ''}
      ${curvaSvg(j)}
    </div>
    <div class="h2g2-prev-rodape">
      ${avisoDivergencia(p)}
      <div class="h2g2-dim h2g2-micro" title="${esc(p.metodo)} · ${esc(p.fonte)}">
        estimado, não medido · erro típico ±${num(erro?.temp_min_c?.erro_medio, 1)}°C (mín.)${erro?.dose_ugy_dia ? ` · ±${num(erro.dose_ugy_dia.erro_medio, 0)} µGy/dia` : ''} · base: ${p.base_origem === 'local' ? `<strong style="color:var(--hud-cyan)">medição do habitat, sol ${esc(p.sol_base)}</strong>` : `PDS, sol ${esc(p.sol_base)}`}${teste}
      </div>
      ${formMedicao(p, msgMedicao)}
    </div>`
}
