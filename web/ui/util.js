import { SLOPE_VERDICT } from '../layers.js'

/** Escapa texto da API antes de ir pra innerHTML. */
export function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
}

/** Número com casas fixas, ou '—' quando a API devolve null (sem dado real). */
export const num = (v, casas = 0) => (v === null || v === undefined ? '—' : Number(v).toFixed(casas))

export const coord = (p) => `${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}`

/** Veredito GO/NO-GO (antes VerdictBadge.tsx). checklist: [{ok, label}]. */
export function veredito(status, checklist = [], rotulo = null) {
  const v = { ...SLOPE_VERDICT[status], ...(rotulo && { label: rotulo }) }
  const itens = checklist
    .map((i) => `<div class="h2g2-mono ${i.ok ? 'ok' : 'falha'}">${i.ok ? '✓' : '⚠'} ${esc(i.label)}</div>`)
    .join('')
  return `<div class="h2g2-veredito" style="--cor:${v.color}">
    <div class="h2g2-display h2g2-veredito-titulo"><span style="font-size:.8em">●</span>${esc(v.label)}</div>
    ${itens && `<div class="h2g2-veredito-check">${itens}</div>`}
  </div>`
}

/** Alertas da feature 08 (api/alertas.py): mesmas cores do veredito. */
const ALERTA_COR = { perigo: 'var(--verdict-perigo)', atencao: 'var(--verdict-atencao)', info: 'var(--ink-3)' }

export const alertasHtml = (alertas) => alertas
  .map((a) => `<div class="h2g2-mono h2g2-alerta" title="fonte: ${esc(a.fonte)}" style="color:${ALERTA_COR[a.nivel]}">● ${esc(a.mensagem)}</div>`)
  .join('')

const MARS_RADIUS_M = 3_396_190

function haversineM(lat1, lon1, lat2, lon2) {
  const rad = (d) => (d * Math.PI) / 180
  const a = Math.sin(rad(lat2 - lat1) / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2
  return MARS_RADIUS_M * 2 * Math.asin(Math.sqrt(a))
}

/** Feição IAU/USGS mais próxima -- client-side, a lista tem ~13 feições. */
export function nomeMaisProximo(feicoes, lat, lon) {
  let melhor = null
  for (const f of feicoes) {
    const d = haversineM(lat, lon, f.lat, f.lon)
    if (!melhor || d < melhor.distance_m) melhor = { feature: f, distance_m: d }
  }
  return melhor
}
