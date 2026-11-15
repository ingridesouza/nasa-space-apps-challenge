import { SLOPE_VERDICT } from '../layers.js'

/** Escapes API text before it goes into innerHTML. */
export function esc(v) {
  return String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
}

/** Number with fixed decimals, or '—' when the API returns null (no real data). */
export const num = (v, decimals = 0) => (v === null || v === undefined ? '—' : Number(v).toFixed(decimals))

export const coord = (p) => `${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}`

/** GO/NO-GO verdict (formerly VerdictBadge.tsx). checklist: [{ok, label}]. */
export function verdict(status, checklist = [], label = null) {
  const v = { ...SLOPE_VERDICT[status], ...(label && { label }) }
  const items = checklist
    .map((i) => `<div class="h2g2-mono ${i.ok ? 'ok' : 'fail'}">${i.ok ? '✓' : '⚠'} ${esc(i.label)}</div>`)
    .join('')
  return `<div class="h2g2-verdict" style="--tone:${v.color}">
    <div class="h2g2-display h2g2-verdict-title"><span style="font-size:.8em">●</span>${esc(v.label)}</div>
    ${items && `<div class="h2g2-verdict-check">${items}</div>`}
  </div>`
}

/** Feature 08 alerts (api/alerts.py): same colors as the verdict. */
const ALERT_COLOR = { danger: 'var(--verdict-danger)', caution: 'var(--verdict-caution)', info: 'var(--ink-3)' }

/** a.distance_m (only in /api/route alerts, not in /api/point ones):
 * actual position along the walk, not the whole route. */
export const alertsHtml = (alerts) => alerts
  .map((a) => `<div class="h2g2-mono h2g2-alert" title="source: ${esc(a.source)}" style="color:${ALERT_COLOR[a.level]}">
    ● ${a.distance_m !== undefined ? `<span class="h2g2-dim">${num(a.distance_m)} m from start:</span> ` : ''}${esc(a.message)}</div>`)
  .join('')

const MARS_RADIUS_M = 3_396_190

function haversineM(lat1, lon1, lat2, lon2) {
  const rad = (d) => (d * Math.PI) / 180
  const a = Math.sin(rad(lat2 - lat1) / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2
  return MARS_RADIUS_M * 2 * Math.asin(Math.sqrt(a))
}

/** Nearest IAU/USGS feature -- client-side, the list has ~13 features. */
export function nearestName(features, lat, lon) {
  let best = null
  for (const f of features) {
    const d = haversineM(lat, lon, f.lat, f.lon)
    if (!best || d < best.distance_m) best = { feature: f, distance_m: d }
  }
  return best
}
