// F02 + F06: route card (real A* over the DTM, per-type weights in api/route_planning.py)
// with the EVA window from the local forecast. The origin is always the current position.
import { deleteMeasurement, getForecast, getRoute, postMeasurement } from '../api.js'
import { SLOPE_COLOR_HEX } from '../layers.js'
import { paginate } from './pages.js'
import { coord, esc, num } from './util.js'

const TYPE_LABEL = { safest: 'Safest', fastest: 'Fastest', most_science: 'Most science' }
// suggestion label (api/route_suggestions.py): fixed rule, not the model
const LABEL = { ok: ['✅', 'no risk on the map'], caution: ['⚠️', 'caution'], danger: ['⛔', 'danger'] }
const routeName = (r) => r.title ?? TYPE_LABEL[r.type] ?? r.type // title: replanning option
const VERDICT = { ok: 'safe', caution: 'caution', danger: 'danger' } // .v-* classes with the system colors

/** F02 + F08: why this route -- pros and cons with source; the suggested one is only the order, all stay clickable. */
function suggestionHtml(r, sg) {
  const s = r.suggestion
  if (!s || !sg) return ''
  const li = (x, cls, sign) => `<li class="${cls}" title="source: ${esc(x.source)}"><b aria-hidden="true">${sign}</b>${esc(x.text)}</li>`
  return `<div class="route-sec suggestion">
    <p class="suggestion-reason v-${VERDICT[sg.summary[0]?.label] ?? 'caution'}"><span class="fl-sec">System suggestion</span>${esc(sg.reason)}</p>
    ${sg.dust_warning ? `<p class="suggestion-reason v-caution">${esc(sg.dust_warning)}</p>` : ''}
    <span class="fl-sec">${LABEL[s.label][0]} ${esc(routeName(r))}${r.type === sg.suggested ? ' · suggested <svg class="h2g2-star" viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" aria-hidden="true" style="vertical-align:-.1em"><polygon points="12.0,0.0 14.2,9.0 23.4,8.3 15.5,13.1 19.1,21.7 12.0,15.7 4.9,21.7 8.5,13.1 0.6,8.3 9.8,9.0"/></svg>' : ' · alternative'}</span>
    <ul class="suggestion-list">${s.pros.map((x) => li(x, 'pro', '+')).join('')}${s.cons.map((x) => li(x, 'con', '!')).join('')}</ul>
    <p class="caption mono" title="${esc(sg.method)}">dashed line on the map = other options${st.previous ? ' and the previous route' : ''} · you decide</p>
  </div>`
}

/** Reference O2 capacity -- simulated, same language as the O2 model in
 * api/route_planning.py (not a suit spec). Editable: there is no suit telemetry. */
const MIN_RESERVE_PCT = 0.2
const DATE = new Intl.DateTimeFormat('en-US', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })
const NAME = { temp_min_c: 'min', temp_max_c: 'max', pressure_pa: 'pressure', ground_noon_c: 'ground', dose_ugy_day: 'radiation' }

const st = {
  origin: null, destination: null, stops: [],
  data: null, error: null, loading: false, type: 'safest',
  capacity: 400,
  solEva: null, fc: undefined, fcKey: null, measureMsg: null,
}
let el, cb
let request = 0
let fcRequest = 0

const kv = (k, v, extra = '') => `<div class="kv"${extra}><span>${k}</span><span>${v}</span></div>`

/** Mini elevation profile -- inline SVG, no lib. */
function profileSvg(profile) {
  if (profile.length < 2) return ''
  const w = 300, h = 48
  const elev = profile.map((p) => p.elevation_m)
  const distMax = profile.at(-1).cumulative_distance_m || 1
  const min = Math.min(...elev)
  const range = Math.max(...elev) - min || 1
  const pts = profile.map((p) => `${((p.cumulative_distance_m / distMax) * w).toFixed(1)},${(h - ((p.elevation_m - min) / range) * h).toFixed(1)}`).join(' ')
  return `<svg class="profile" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Elevation profile: ${num(min, 0)} to ${num(min + range, 0)} m">
    <polyline points="${pts}" fill="none" stroke="var(--b300)" stroke-width="1.5" vector-effect="non-scaling-stroke"/></svg>`
}

/** Day curve (inline SVG) with the EVA window highlighted. */
function curveSvg(win) {
  const pts = Object.entries(win?.hourly_curve ?? {}).map(([h, t]) => [Number(h), t]).sort((a, b) => a[0] - b[0])
  if (pts.length < 2) return '<p class="caption mono">no hourly curve for this sol</p>'
  const W = 300, H = 64, P = 4
  const ts = pts.map((p) => p[1])
  const [tmin, tmax] = [Math.min(...ts), Math.max(...ts)]
  const x = (h) => P + (h / 23) * (W - 2 * P)
  const y = (t) => P + (1 - (t - tmin) / (tmax - tmin || 1)) * (H - 2 * P - 10)
  const start = Number(win.start_lmst.slice(0, 2))
  const end = start + win.hours
  const line = pts.map(([h, t], i) => `${i ? 'L' : 'M'}${x(h).toFixed(1)},${y(t).toFixed(1)}`).join(' ')
  return `<svg class="curve" viewBox="0 0 ${W} ${H}" role="img"
      aria-label="Forecast temperature by hour: from ${num(tmin, 0)} to ${num(tmax, 0)} °C; best window ${esc(win.start_lmst)}–${esc(win.end_lmst)}">
    <rect x="${x(start)}" y="0" width="${Math.max(x(Math.min(end, 23)) - x(start), 3)}" height="${H - 10}" class="curve-window"/>
    <path d="${line}" class="curve-line"/>
    ${[0, 6, 12, 18].map((h) => `<text x="${x(h)}" y="${H - 1}" class="curve-axis">${h}h</text>`).join('')}
    <text x="${W - P}" y="${y(tmax) + 3}" class="curve-axis" text-anchor="end">${num(tmax, 0)}°</text>
    <text x="${W - P}" y="${y(tmin)}" class="curve-axis" text-anchor="end">${num(tmin, 0)}°</text>
  </svg>`
}

/** O₂ in a single bar: outbound and round trip (same cost: the speed model only
 * depends on the slope magnitude, not its direction). */
function o2Html(r) {
  const cap = st.capacity
  const limit = (1 - MIN_RESERVE_PCT) * cap
  const pct = (l) => Math.min(100, (l / cap) * 100)
  const out = r.estimated_o2_l, back = r.estimated_o2_l * 2
  const color = (l) => (l <= limit ? 'var(--ok)' : 'var(--mars2)')
  return `<div class="route-sec">
    <div class="sci-top"><span class="sci-sec">Estimated O₂ · simulated</span>
      <label class="o2-cap mono">suit <input type="number" min="1" step="1" value="${cap}" data-field="o2-capacity" aria-label="Suit O₂ capacity in liters"> L</label></div>
    <div class="o2" role="img" aria-label="Outbound ${num(out, 1)} L, round trip ${num(back, 1)} L of ${cap} L">
      <div class="o2-return" style="width:${pct(back)}%;background:${color(back)}"></div>
      <div class="o2-out" style="width:${pct(out)}%;background:${color(out)}"></div>
      <div class="o2-reserve" style="left:${100 - MIN_RESERVE_PCT * 100}%" title="20% minimum reserve"></div>
    </div>
  </div>`
}

function routeDetail(r, top = '') {
  const target = r.science_target
  return `${o2Html(r)}
    ${top}
    ${target ? `<div class="route-sec"><span class="sci-sec">Passes near</span>
      <button type="button" class="target-btn" data-action="target">◇ ${esc(target.name)} <span class="mono">open science card ›</span></button></div>` : ''}`
}

/** F06: "couple the forecast to the route, suggesting the best window for the EVA". */
function loadForecast(key, minutes) {
  const mine = ++fcRequest
  st.fcKey = key
  st.fc = undefined
  getForecast({ duration_min: minutes, ...(st.solEva && { sol: st.solEva }) })
    .catch(() => null)
    .then((p) => {
      if (mine !== fcRequest) return
      st.fc = p
      render()
    })
}

function measureForm(p) {
  const local = p?.local_measurement
  return `<details class="measure"${st.measureMsg ? ' open' : ''}>
    <summary class="mono">＋ habitat measurement</summary>
    <form data-measure>
      <label>sol <input name="sol" type="number" min="1" step="1" required value="${esc(local?.sol ?? p?.sol ?? '')}"></label>
      <label>min °C <input name="temp_min_c" type="number" step="0.1" required></label>
      <label>max °C <input name="temp_max_c" type="number" step="0.1" required></label>
      <label>Pa <input name="pressure_pa" type="number" step="0.1" required></label>
      <label>µGy/day <input name="dose_ugy_day" type="number" step="1" placeholder="optional"></label>
      <button class="btn btn-sm">save</button>
      ${local ? `<button type="button" class="link-btn" data-delete-measurement="${esc(local.sol)}">delete measurement for sol ${esc(local.sol)}</button>` : ''}
    </form>
    ${st.measureMsg ? `<p class="caption mono" role="status">${esc(st.measureMsg)}</p>` : ''}
  </details>`
}

function evaSection(r) {
  const minutes = r.estimated_time_min * 2 // EVA = outbound + return (same time both ways, see o2Html)
  const key = `${st.solEva}|${minutes}`
  if (st.fcKey !== key) loadForecast(key, minutes)
  const p = st.fc
  const sol = st.solEva ?? p?.sol ?? ''
  const top = `<div class="sci-top"><span class="sci-sec">EVA window · ${esc(Math.ceil(minutes / 60))}h</span>
    <span class="sol-step mono">
      <button type="button" data-sol-step="-1" aria-label="Previous sol">‹</button>
      <label>sol <input type="number" data-sol-eva min="1" step="1" value="${esc(sol)}" aria-label="EVA sol"></label>
      <button type="button" data-sol-step="1" aria-label="Next sol">›</button>
    </span></div>`
  let body
  if (p === undefined) body = '<p class="empty">computing from the local forecast…</p>'
  else if (p === null) body = '<p class="empty error">Failed to fetch the forecast.</p>'
  else if (!p.temp_min_c || !p.temp_max_c) body = `<p class="empty">No forecast for sol ${esc(p.sol)}: no previous year measured in this season.</p>`
  else {
    const j = p.eva_window
    const evaDose = p.dose_ugy_day ? (p.dose_ugy_day.value / 24) * (minutes / 60) : null
    const error = p.backtest_error
    const div = p.divergence?.length
      ? `<p class="caption mono warning" role="alert">⚠ Measurement for sol ${esc(p.local_measurement.sol)} outside the season's normal (${p.divergence.map((d) => `${NAME[d.field] ?? esc(d.field)} ${num(d.measured, 0)} measured × ${num(d.expected, 0)} expected`).join(' · ')}). The forecast is less reliable until the weather returns to normal.</p>`
      : ''
    body = `${j ? `<p class="eva-time">${esc(j.start_lmst)}–${esc(j.end_lmst)} <small class="mono">local solar time · coldest hour ${num(j.coldest_temp_in_window_c, 0)} °C</small></p>` : '<p class="empty">no hourly curve to forecast the window</p>'}
      ${curveSvg(j)}
      ${kv('Air', `${num(p.temp_min_c.value, 0)}° to ${num(p.temp_max_c.value, 0)} °C`)}
      ${p.ground_noon_c ? kv('Ground 12h', `~${num(p.ground_noon_c.value, 0)} °C`) : ''}
      ${p.pressure_pa ? kv('Pressure', `${num(p.pressure_pa.value, 0)} Pa`) : ''}
      ${p.dose_ugy_day ? kv('Radiation', `${num(p.dose_ugy_day.value, 0)} µGy/day`) : ''}
      ${evaDose !== null ? kv('Dose this EVA', `~${num(evaDose, 1)} µGy`) : ''}
      ${div}
      <p class="caption mono" title="${esc(p.method)} · ${esc(p.source)}">${p.earth_date ? `${esc(DATE.format(new Date(`${p.earth_date}T12:00:00Z`)))} on Earth · Ls ${num(p.ls, 0)}° · ` : ''}estimated, not measured · typical error ±${num(error?.temp_min_c?.mean_error, 1)} °C (min)${error?.dose_ugy_day ? ` · ±${num(error.dose_ugy_day.mean_error, 0)} µGy/day` : ''} · base: ${p.base_origin === 'local' ? `habitat measurement, sol ${esc(p.base_sol)}` : `PDS, sol ${esc(p.base_sol)}`}</p>`
  }
  return `<div class="route-sec">${top}${body}${p ? measureForm(p) : ''}</div>`
}

const activeRoute = () => st.data?.routes.find((r) => r.type === st.type) ?? null
// the other options and, after a replanning, the route that was being followed: all dashed on the map
const otherRoutes = () => [...(st.data?.routes.filter((r) => r.type !== st.type) ?? []), ...(st.previous ? [st.previous] : [])]
const endOf = (r) => ({ lat: r.points.at(-1)[0], lon: r.points.at(-1)[1] })

/** F02 + F08: options from /api/replan (problem reported in the middle of the walk). Same card as the
 * variants; the route that was open stays dashed on the map. Nothing is chosen on its own. */
export function showOptions(res, origin) {
  const previous = st.previous ?? activeRoute()
  request++ // discards a route computation in progress
  const suggested = res.routes.find((r) => r.type === res.suggestion.suggested) ?? res.routes[0]
  Object.assign(st, { origin, destination: endOf(suggested), stops: [], data: res, error: null, loading: false, type: suggested.type, previous })
  render()
  cb.onActiveRoute(activeRoute(), otherRoutes())
}

/** F08: the open route, in the format /api/ask expects; null with no computed route. */
export function routeForAgent() {
  const { origin: o, destination: d } = st
  if (!activeRoute() || !o || !d) return null
  // replanning option: the forecast recomputes by the A* weight (variant), not by the option id
  return { origin_lat: o.lat, origin_lon: o.lon, dest_lat: d.lat, dest_lon: d.lon, type: activeRoute().variant ?? st.type, ...(st.solEva && { sol: st.solEva }) }
}

function render() {
  let body
  // legend for the track colors (same bands as api/route_planning.py)
  const legend = st.data ? `<div class="route-legend mono"><span class="legend-title">Slope</span><div>${[['safe', '< 15°'], ['caution', '15–20°'], ['danger', '≥ 20°']]
    .map(([k, t]) => `<span><i style="background:${SLOPE_COLOR_HEX[k]}"></i>${t}</span>`).join('')}</div></div>` : ''
  const top = st.destination ? `<div class="route-sec route-top">${legend}<span><button type="button" class="link-btn" data-action="mark-position" title="no GPS: click the map where you are; replanning starts there">📍 I am here</button> <button type="button" class="link-btn" data-action="add-stop">+ stop along the way</button></span></div>` : ''
  if (!st.destination) body = '<p class="empty">Click the map or type the destination coordinates.</p>'
  else {
    body = `<div class="route-sec">
      ${st.stops.map((p, i) => kv(`Stop ${i + 1}`, `${coord(p)} <button type="button" class="link-btn" data-action="remove-stop" data-i="${i}" aria-label="Remove stop ${i + 1}">×</button>`)).join('')}
      ${kv('Destination', coord(st.destination))}
      ${activeRoute() ? kv('Route length', `${num(activeRoute().distance_m)} m`) + kv('Time · round trip', `~${num(activeRoute().estimated_time_min * 2)} min`) : ''}
    </div>`
    if (!cb.mapReady()) body += '<p class="empty loading" role="status"><i class="spinner"></i>loading the map… the track appears as soon as it finishes</p>'
    if (st.loading) body += '<p class="empty loading" role="status"><i class="spinner"></i>computing route (A* over the DTM)…</p>'
    if (st.error) body += `<p class="empty error">${esc(st.error)}</p>`
    if (st.data) {
      body += `<div class="types">${st.data.routes
        .map((r) => {
          const [icon, txt] = LABEL[r.suggestion?.label] ?? ['', '']
          return `<button type="button" class="type ${r.type === st.type ? 'on' : ''}" data-type="${r.type}" aria-label="${esc(routeName(r))}: ${txt}">${icon} ${esc(routeName(r))}${r.type === st.data.suggestion?.suggested ? ' ★' : ''}<small class="type-meta">${num(r.distance_m, 0)} m · ${num(r.estimated_time_min, 0)} min</small></button>`
        }).join('')}</div>`
      const r = activeRoute()
      if (st.data.problem_text) {
        body = `<div class="route-sec"><p class="suggestion-reason v-danger"><span class="fl-sec">Problem reported · new options</span>${esc(st.data.problem_text)}</p></div>` + body
      }
      if (r) body += suggestionHtml(r, st.data.suggestion) + routeDetail(r, top)
    }
    if (!activeRoute()) body += top // no route computed yet: the stop button is already at hand
  }
  el.innerHTML = `<div class="route-wrap">
    <div class="route-body">${body}
      <button type="button" class="link-btn route-cancel page-fixed" data-action="cancel">✕ cancel route</button></div>
  </div>`
  // F11: no scrolling; card sections become pages (‹ 1/3 ›)
  paginate(el, { sel: ':scope > .route-wrap > .route-body > *', max: () => Math.min(innerHeight - 40, 560) })
}

/** callbacks: onCancel(), onActiveRoute(route|null, others[]), onAddStop(), onMarkPosition(), onRemoveStop(i), onOpenTarget(target). */
export function initRoute(container, callbacks) {
  el = container
  cb = callbacks
  el.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-action],[data-type],[data-sol-step],[data-delete-measurement]')
    if (!b) return
    if (b.dataset.type) {
      st.type = b.dataset.type
      if (st.data?.problem) st.destination = endOf(activeRoute()) // a return option ends at the base, not at the destination
      cb.onActiveRoute(activeRoute(), otherRoutes())
    } else if (b.dataset.solStep) {
      const base = st.solEva ?? st.fc?.sol
      if (base) st.solEva = Math.max(1, base + Number(b.dataset.solStep))
    } else if (b.dataset.deleteMeasurement) {
      await deleteMeasurement(b.dataset.deleteMeasurement)
      st.measureMsg = `measurement for sol ${b.dataset.deleteMeasurement} deleted`
      st.fcKey = null
    } else {
      const a = b.dataset.action
      if (a === 'cancel') return cb.onCancel()
      if (a === 'add-stop') return cb.onAddStop()
      if (a === 'mark-position') return cb.onMarkPosition()
      if (a === 'remove-stop') return cb.onRemoveStop(Number(b.dataset.i))
      if (a === 'target') return cb.onOpenTarget(activeRoute()?.science_target)
    }
    render()
  })
  el.addEventListener('toggle', (e) => {
  }, true)
  // 'change' (not 'input'): render() replaces innerHTML and would drop focus on every keystroke
  el.addEventListener('change', (e) => {
    const v = Number(e.target.value)
    if (e.target.dataset.field === 'o2-capacity' && v > 0) st.capacity = v
    else if (e.target.matches('[data-sol-eva]') && Number.isInteger(v) && v >= 1) st.solEva = v
    else return
    render()
  })
  // habitat measurement: becomes the forecast base, without Earth
  el.addEventListener('submit', async (e) => {
    if (!e.target.matches('[data-measure]')) return
    e.preventDefault()
    const values = Object.fromEntries([...new FormData(e.target)].filter(([, v]) => v !== '').map(([k, v]) => [k, Number(v)]))
    try {
      const m = await postMeasurement(values)
      st.measureMsg = `measurement for sol ${m.sol} saved: subsequent forecasts start from it`
    } catch (err) {
      st.measureMsg = err.message
    }
    st.fcKey = null
    render()
  })
  async function updateRoute(origin, destination, stops = []) {
    Object.assign(st, { origin, destination, stops, data: null, error: null, loading: Boolean(origin && destination), previous: null })
    const mine = ++request
    cb.onActiveRoute(null)
    render()
    if (!st.loading) return
    try {
      const data = await getRoute(origin, destination, stops)
      if (mine !== request) return // points changed mid-computation
      st.data = data
      st.type = data.suggestion?.suggested ?? 'safest'
    } catch (e) {
      if (mine !== request) return
      st.error = e.message
    }
    st.loading = false
    cb.onActiveRoute(activeRoute(), otherRoutes())
    render()
    return st.data // F08 voice: the spoken summary comes from these numbers
  }
  updateRoute.redraw = render
  return updateRoute
}
