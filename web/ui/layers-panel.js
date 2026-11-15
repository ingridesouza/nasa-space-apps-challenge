// Compact layer selector (expanded map only). CTX and HiRISE (group 'base')
// are always on at 100% and do not appear here. Events in app.js via
// data-toggle / data-opacity.
import { CONTINUOUS_SCALE, TI_LEGEND, TOGGLEABLE_LAYERS } from '../layers.js'
import { atmosphereRange } from '../map.js'
import { esc } from './util.js'

function row(id, on, label, title = '') {
  return `<div class="lyr-row">
      <button type="button" role="switch" aria-checked="${on}" aria-label="${esc(label)}" data-toggle="${id}" class="sw ${on ? 'on' : ''}"><span></span></button>
      <span class="lyr-name" title="${esc(title)}">${esc(label)}</span>
    </div>`
}

function tiLegend() {
  return `<div class="lyr-legend" title="Thermal inertia (J m⁻² K⁻¹ s⁻½), THEMIS/USGS, 100 m per cell">
      <span class="lyr-grad" style="background:${TI_LEGEND.gradient}"></span>
      <span class="mono">${TI_LEGEND.min} loose</span><span class="mono">firm ${TI_LEGEND.max}</span>
    </div>`
}

const MARS_HOUR_S = 3698.968 // 1/24 of a sol in seconds (api/mars_time.py)
export const hhmm = (h) => {
  const m = Math.round((((h % 24) + 24) % 24) * 60)
  return `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}
/** Local solar time of arrival at the destination: now + route outbound time (Earth minutes). */
export function arrivalHour(state) {
  if (!state.clock || !state.route?.estimated_time_min) return null
  return (state.clock.ltst + (state.route.estimated_time_min * 60) / MARS_HOUR_S) % 24
}

const SUN_CATEGORY = { sun: 'in sun', partial: 'partial shade', shade: 'in shade' }
function destinationLine(info) {
  if (!info?.category) return ''
  return `<span class="lyr-note lyr-highlight">Destination: ${SUN_CATEGORY[info.category]}</span>`
}

/** state.insolation = {hour, info}: solar hour (now/arrival shortcuts) + Sun + destination. */
function insolationLegend(state) {
  const { hour, info } = state.insolation
  const now = state.clock?.ltst ?? null
  const arrival = arrivalHour(state)
  const shortcut = (target, label) => `<button type="button" class="lyr-shortcut ${Math.abs(target - hour) < 0.13 ? 'on' : ''}" data-insol-go="${target}">${label}</button>`
  const title = 'Inferred from relief (Mars24 + HiRISE DTM + MOLA). Light guidance, not a safety criterion. See README.'
  return `<div class="lyr-legend" title="${title}">
      <span class="lyr-note">${now !== null ? shortcut(now, `now ${hhmm(now)}`) : ''}${arrival !== null ? shortcut(arrival, `arrival ${hhmm(arrival)}`) : ''}</span>
      <label class="lyr-note mono">${hhmm(hour)}${info ? ` · Sun at ${Math.round(info.sun_elevation)}°` : ''}
        <input type="range" class="lyr-hour" min="5" max="19" step="0.25" value="${hour}" data-insol-hour aria-label="Local solar time"></label>
      ${destinationLine(info)}
      <span class="lyr-grad" style="background:linear-gradient(90deg, rgb(15,20,60) 0 18%, rgb(60,110,190) 18%, rgb(245,205,70))"></span>
      <span class="mono">shade</span><span class="mono">sun</span>
    </div>`
}

/** state.atmosphere = {geo, variable}: variable selector + measured range. */
function atmosphereLegend({ geo, variable, error }) {
  if (error) return `<p class="caption mono">no atmospheric data: ${esc(error)}</p>`
  if (!geo) return '<p class="caption mono">loading REMS…</p>'
  const { unit } = geo.variables[variable]
  const range = atmosphereRange(geo, variable)
  const n = geo.features.filter((f) => f.properties[variable] !== null).length
  const options = Object.entries(geo.variables).map(([k, v]) => `<li role="option" tabindex="-1" class="lyr-opt ${k === variable ? 'on' : ''}" data-atm-var="${k}" aria-selected="${k === variable}">${esc(v.label)}</li>`).join('')
  return `<div class="lyr-legend" title="${esc(`${geo.source}. ${geo.note}`)}">
      <div class="lyr-sel">
        <button type="button" class="lyr-sel-btn" data-atm-open aria-haspopup="listbox" aria-expanded="false" aria-label="Atmospheric variable">${esc(geo.variables[variable].label)}</button>
        <ul class="lyr-menu" role="listbox" hidden>${options}</ul>
      </div>
      <span class="lyr-grad" style="background:linear-gradient(90deg, ${CONTINUOUS_SCALE.join(', ')})"></span>
      <span class="mono">${range ? `${range[0]} ${esc(unit)}` : '—'}</span><span class="mono">${range ? `${range[1]} ${esc(unit)}` : '—'}</span>
      <span class="lyr-note">${n} sols · gray = no data</span>
    </div>`
}

/** state: { layers: {id: {visible, opacity}} } */
export function renderLayers(el, state) {
  el.innerHTML = `
    ${TOGGLEABLE_LAYERS.filter((l) => l.group !== 'base').map((l) => row(l.id, state.layers[l.id].visible, l.label, '')).join('')}
    ${state.layers.themis_ti?.visible ? tiLegend() : ''}
    ${state.layers.insolation?.visible ? insolationLegend(state) : ''}
    ${state.layers.atmosphere_track?.visible ? atmosphereLegend(state.atmosphere) : ''}`
}
