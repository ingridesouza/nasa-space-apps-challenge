// H2G2 · front orchestration. Viewer (F03/F04) full screen; map (F01) in a circle
// that expands; route (F02 + F06) in a card; assistant (F08) at the top.
// The current position comes from the tracker (simulated at /api/position) and is the route origin.
import {
  getAtmosphereTrack, getConditions, getScienceCard, getInsolation, getClock, getPhotosNear, getLayers, getPanorama,
  getPoint, getPosition,
} from './api.js'
import { TOGGLEABLE_LAYERS } from './layers.js'
import * as map from './map.js'
import { initAssistant } from './ui/agent.js'
import { initAnswerCard } from './ui/answer-card.js'
import { arrivalHour, renderLayers } from './ui/layers-panel.js'
import { initRoute, routeForAgent, showOptions } from './ui/route.js'
import { initVoice } from './ui/voice.js'
import { context, describeOpen, execute, initCommands, register } from './ui/commands.js'
import { changePage, paginate } from './ui/pages.js'
import { esc } from './ui/util.js'

const $ = (id) => document.getElementById(id)
const mobile = () => matchMedia('(max-width:900px)').matches
const TRANSITION_MS = 260 // same as the .map-box transition in style.css

const state = {
  position: null, // {lat, lon, label}
  place: null, // what the viewer and cards show: position or destination
  map: 'viewer', // 'viewer' (circle) | 'explore' | 'route'
  routeActive: false,
  destination: null,
  stops: [],
  route: null,
  layers: Object.fromEntries(TOGGLEABLE_LAYERS.map((l) => [l.id, { visible: l.defaultVisible, opacity: l.defaultOpacity }])),
  insolation: { hour: 9, info: null, started: false }, // direct sun and shade layer: local solar time
  clock: null, // simulated mission clock (/api/clock): {sol, ltst}
  atmosphere: { geo: null, variable: 'temp_max_c' }, // REMS points layer (GeoJSON from /api/atmosphere/track)
}
let awaitingStop = false
let awaitingPosition = false // "📍 I am here": the next click becomes the astronaut's position (no GPS)

// ---------------- Place (position or destination): status, panorama, photos, answer card ----------------
let placeSeq = 0
let last = null // {pano} of the current place, to redraw the status
let answersShown = 0 // a question asked while a place loads must not be overwritten by that place's science card

async function loadPlace(place) {
  const mine = ++placeSeq
  const answersAtStart = answersShown
  state.place = place
  loading()
  answerCard.showPlace('loading')
  const { lat, lon } = place
  const [pano, photos, science] = (await Promise.allSettled([
    getPanorama(lat, lon), getPhotosNear(lat, lon), getScienceCard(lat, lon),
  ])).map((r) => (r.status === 'fulfilled' ? r.value : null))
  if (mine !== placeSeq) return // another place already replaced this one
  last = { pano }
  map.setPanorama(pano?.found ? pano : null)
  if (pano) showPano(pano)
  else clearPano()
  if (answersShown === answersAtStart) answerCard.showPlace(science ?? 'error')
  if (photos) showPhotos(photos)
  else $('c-photos').hidden = true
}

// images bar empty (and closed by the CSS :has) until there is a destination with a computed route
function clearBar() {
  placeSeq++
  state.place = null
  last = null
  clearPano()
  closePhoto()
  map.setPanorama(null)
  for (const id of ['c-status', 'c-photos', 'c-answer']) $(id).hidden = true
  collapseGroup('g-images', false)
}

const samePoint = (a, b) => a && b && a.lat === b.lat && a.lon === b.lon

function loading() {
  for (const id of ['c-pano', 'c-photos', 'c-answer']) $(id).hidden = true
}

function card(id, html) { $(id).innerHTML = html; $(id).hidden = false }

// ---------------- Conditions / planet-level alerts (feature 05 + 08) ----------------
// Fixed-rule alerts from api/alerts.py (dust season, stale data, solar
// particle event -- see docs/feature-05-solar-particle-event.md); the
// model never creates or cancels one of these, same as every other alert
// in the system. Reuses the same .suggestion-reason.v-* styling the route
// card already uses for its own alerts (visual language stays consistent).
function renderConditions(data) {
  if (!data?.alerts?.length) { $('c-status').hidden = true; return }
  const rows = data.alerts
    .map((a) => `<p class="suggestion-reason v-${a.level === 'danger' ? 'danger' : a.level === 'caution' ? 'caution' : 'safe'}" title="source: ${esc(a.source)}">${esc(a.message)}</p>`)
    .join('')
  card('c-status', rows)
}

// ---------------- Panorama ----------------
let viewer = null // preview (always in the panel)
let viewerBg = null // copy in the viewer
let panoCfg = null
let pointYaw = 0
// pannellum keeps the DOM element inside the hotspot: each viewer needs its own object, otherwise one moves the other's marker
const hotSpots = () => [{ pitch: 0, yaw: pointYaw, type: 'info', text: 'direction of the given point' }]
let inViewer = false
// preview more zoomed in; in the background, back to 90° and tilt a bit toward the image center
const HFOV_PREVIEW = 65, HFOV_BG = 90, CENTER_BG = 0.5, CENTER_PREVIEW = 0.3
let voff = 0
let panoSeq = 0
// pannellum only repositions the marker on window resize; a container that changes size (bar collapses/expands) leaves it off
const roPano = new ResizeObserver((es) => {
  for (const e of es) {
    const v = e.target.id === 'pano-bg' ? viewerBg : viewer
    if (v && e.contentRect.width) v.resize()
  }
})

function clearPano() {
  panoSeq++
  if (inViewer) closeViewer()
  if (viewer) { viewer.destroy(); viewer = null }
  $('pano').innerHTML = ''
  $('c-pano').hidden = true
}

function showPano(p) {
  clearPano()
  if (!p.found) return
  $('c-pano').hidden = false
  $('pano-caption').textContent = `${p.label} · ${p.credit}`
  voff = p.pannellum.vOffset || 0
  panoCfg = Object.assign({}, p.pannellum, {
    showControls: false, compass: false,
  })
  pointYaw = p.pannellum.yaw
  // create the viewer only after the card paints: pannellum init is heavy and froze the animation
  const seq = panoSeq
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (seq !== panoSeq) return
    viewer = pannellum.viewer('pano', Object.assign({}, panoCfg, { hotSpots: hotSpots(), hfov: HFOV_PREVIEW, pitch: voff * CENTER_PREVIEW }))
    roPano.observe($('pano'))
  }))
}

// two independent bars in the right column (route and images), each with its own button
function collapseGroup(id, c) {
  const g = $(id)
  g.classList.toggle('collapsed', c)
  const t = g.querySelector('.group-toggle')
  t.textContent = c ? '‹' : '›'
  t.title = `${c ? 'Expand' : 'Collapse'} ${t.dataset.name}`
  t.setAttribute('aria-expanded', String(!c))
  if (id === 'g-route' && !c) requestAnimationFrame(() => paginate($('c-route'))) // hidden, it measured 0 px
  if (id === 'g-images') {
    $('answer-cards').classList.toggle('collapsed', c)
    if (!c) requestAnimationFrame(() => { viewer?.resize(); placeAnswerCards() }) // pannellum measured 0 px while hidden
  }
}
// answer card left of the images bar (bottom, CSS); on mobile it sits above the bottom sheet
function placeAnswerCards() {
  const f = $('answer-cards')
  f.style.bottom = mobile() ? innerHeight - $('floating').getBoundingClientRect().top + 8 + 'px' : ''
}
{
  const ro = new ResizeObserver(placeAnswerCards)
  for (const id of ['floating', 'c-route', 'c-status', 'c-pano', 'c-photos']) ro.observe($(id))
  addEventListener('resize', placeAnswerCards)
  $('floating').addEventListener('scroll', placeAnswerCards)
}
for (const t of document.querySelectorAll('.group-toggle')) {
  t.addEventListener('click', () => { const g = t.parentElement; collapseGroup(g.id, !g.classList.contains('collapsed')) })
}

// the viewer gets a 2nd pannellum viewer (same image, current yaw); the preview stays in the panel
function expand() {
  if (!viewer) return
  collapseGroup('g-images', true)
  closePhoto()
  const d = document.createElement('div')
  d.id = 'pano-bg'
  $('viewer-stage').appendChild(d)
  viewerBg = pannellum.viewer('pano-bg', Object.assign({}, panoCfg, {
    hotSpots: hotSpots(), hfov: HFOV_BG, pitch: voff * CENTER_BG, yaw: viewer.getYaw(),
  }))
  roPano.observe(d)
  $('viewer-close').hidden = false
  inViewer = true
  viewerInFront(true)
  // take focus off the button (now in the collapsed bar) and hand it to the panorama
  if (document.activeElement) document.activeElement.blur()
  d.tabIndex = 0
  d.focus({ preventScroll: true })
}
function collapse() {
  if (viewerBg) { viewerBg.destroy(); viewerBg = null }
  $('pano-bg')?.remove()
  $('viewer-close').hidden = true
  inViewer = false
  collapseGroup('g-images', false)
}
// click (without dragging) on the preview: opens the panorama in the viewer; clicking again closes it
{
  let start = null
  const slot = document.querySelector('.pano-slot')
  slot.addEventListener('pointerdown', (e) => { start = [e.clientX, e.clientY] }, true)
  slot.addEventListener('pointerup', (e) => {
    if (!start) return
    const drag = Math.hypot(e.clientX - start[0], e.clientY - start[1])
    start = null
    if (drag > 5 || e.target.closest('.pnlm-controls-container')) return
    inViewer ? closeViewer() : expand()
  }, true)
}

// ---------------- Photos ----------------
const PHOTOS_PER_PAGE = 3
let photoList = [], photoPage = 0

function showPhotos(f) {
  $('c-photos').hidden = !f.total
  if (!f.total) return
  photoList = f.photos
  photoPage = 0
  renderPhotos(0)
}

function renderPhotos(dir) {
  const total = Math.max(1, Math.ceil(photoList.length / PHOTOS_PER_PAGE))
  photoPage = Math.min(Math.max(photoPage, 0), total - 1)
  const box = $('photos')
  box.innerHTML = ''
  for (const ph of photoList.slice(photoPage * PHOTOS_PER_PAGE, (photoPage + 1) * PHOTOS_PER_PAGE)) {
    const b = document.createElement('button')
    b.type = 'button'; b.className = 'photo'; b.title = ph.label
    b.innerHTML = `<img loading="lazy" src="${esc(ph.thumb)}" alt=""><p>${ph.distance_m < 5 ? '&lt; 10' : `~${Math.round(ph.distance_m / 10) * 10}`} m · ${esc(ph.instrument)}</p>`
    b.onclick = () => openPhoto(ph)
    box.appendChild(b)
  }
  box.classList.remove('slide-next', 'slide-prev')
  if (dir) { void box.offsetWidth; box.classList.add(dir > 0 ? 'slide-next' : 'slide-prev') }
  $('photos-nav').hidden = total <= 1
  $('photos-page').textContent = `${photoPage + 1} / ${total}`
  $('photos-prev').disabled = photoPage === 0
  $('photos-next').disabled = photoPage === total - 1
}
$('photos-prev').addEventListener('click', () => { photoPage--; renderPhotos(-1) })
$('photos-next').addEventListener('click', () => { photoPage++; renderPhotos(1) })

let openedPhoto = null
function openPhoto(ph) {
  if (openedPhoto === ph && !$('viewer-img').hidden) return closeViewer() // 2nd click closes
  openedPhoto = ph
  if (inViewer) collapse()
  $('viewer-img').src = ph.img
  $('viewer-img').alt = ph.label
  $('viewer-img').hidden = false
  $('viewer-close').hidden = false
  viewerInFront(true)
}
// with the map expanded, the viewer (photo/panorama) overlays it; closing returns to the map
function viewerInFront(v) { document.body.classList.toggle('viewer-front', v) }
function closePhoto() {
  openedPhoto = null
  $('viewer-img').hidden = true
  $('viewer-img').removeAttribute('src')
  $('viewer-close').hidden = !inViewer
}
function closeViewer() { if (inViewer) collapse(); closePhoto(); viewerInFront(false) }
$('viewer-close').addEventListener('click', closeViewer)

// ---------------- Answer card (F08, ui/answer-card.js; replaced the F04 science card) ----------------
// structured answer to the question asked during the walk; with no question, the destination science card
const answerCard = initAnswerCard($('c-answer'), {
  onRouteType: (type) => {
    if (!state.route) return
    collapseGroup('g-route', false)
    $('c-route').querySelector(`[data-type="${type}"]`)?.click()
  },
  onRender: () => placeAnswerCards(),
})
addEventListener('resize', () => { answerCard.paginate(); paginate($('c-route')); paginate($('assistant')) })

// ---------------- Map: circle <-> full screen ----------------
const layers = () => renderLayers($('layers-panel'), state)

function afterTransition(fn) { setTimeout(fn, TRANSITION_MS) }

function instruction(text) {
  $('instruction').hidden = !text
  $('instruction').textContent = text ?? ''
}

function openMap(mode) {
  state.map = mode
  document.body.classList.add('map-open')
  viewerInFront(false)
  $('map-box').removeAttribute('title')
  layers()
  $('layers-panel').hidden = false
  $('coords').hidden = mode !== 'route'
  map.setMode(mode)
  if (mode === 'route') {
    if (!state.routeActive) {
      state.routeActive = true // route card only appears with a destination (the instruction already guides the click)
      updateRoute(state.position, null, [])
    }
    if (!state.destination) instruction('click the map or type the DESTINATION coordinates')
  }
  afterTransition(() => { map.resize(); map.center(state.destination ?? state.position, state.route) })
}

function closeMap() {
  state.map = 'viewer'
  awaitingStop = awaitingPosition = false
  document.body.classList.remove('map-open')
  $('map-box').title = 'Expand map'
  for (const id of ['layers-panel', 'coords', 'readout']) $(id).hidden = true
  instruction(null)
  map.setMode('viewer')
  let pending = Promise.resolve()
  if (state.routeActive && !state.destination) cancelRoute()
  afterTransition(() => {
    map.resize()
    map.center(state.destination ?? state.position, state.route)
    viewer?.resize()
  })
  return pending
}

$('map-box').addEventListener('click', () => { if (state.map === 'viewer') openMap('explore') })
$('btn-route').addEventListener('click', () => openMap('route'))

// ---------------- Route ----------------
const updateRoute = initRoute($('c-route'), {
  onCancel: cancelRoute,
  mapReady: map.mapReady,
  onActiveRoute: (r, others = []) => {
    state.route = r
    if (r?.title) { // replanning option: the flag follows the end of the chosen option
      state.destination = { lat: r.points.at(-1)[0], lon: r.points.at(-1)[1] }
      map.setDestination(state.destination)
    }
    map.setRoute(r, others)
    if (state.layers.insolation.visible) updateInsolation() // destination/arrival changed
    if (r && state.map === 'viewer') map.center(null, r)
    // route computed: the bar opens with panorama, photos and science card of the DESTINATION (not the origin)
    if (r && state.destination && !samePoint(state.place, state.destination)) {
      loadPlace({ ...state.destination, kind: 'destination', label: 'the route destination' })
    }
  },
  onAddStop: () => {
    if (state.map !== 'route') openMap('route')
    awaitingStop = true
    instruction('click the map to add the STOP')
  },
  onMarkPosition: () => {
    if (state.map !== 'route') openMap('route')
    awaitingPosition = true
    instruction('click the map WHERE YOU ARE')
  },
  onRemoveStop: (i) => {
    state.stops.splice(i, 1)
    map.setStops(state.stops)
    updateRoute(state.position, state.destination, state.stops)
  },
  onOpenTarget: async (target) => {
    if (!target?.lat) return
    if (state.map !== 'viewer') await closeMap()
    getScienceCard(target.lat, target.lon).then((f) => answerCard.showPlace(f, true), () => answerCard.showPlace('error', true))
  },
})

function setDestination(p) {
  if (!samePoint(state.place, p)) clearBar() // previous destination data goes away right now
  $('c-route').hidden = false
  collapseGroup('g-route', false)
  state.destination = p
  state.stops = []
  map.setDestination(p)
  map.setStops([])
  instruction(null)
  $('btn-route').textContent = 'Edit route'
  return updateRoute(state.position, p, []) // F08 voice: the spoken summary comes from these numbers
}

function cancelRoute() {
  Object.assign(state, { routeActive: false, destination: null, stops: [], route: null })
  if (state.layers.insolation.visible) updateInsolation()
  awaitingStop = awaitingPosition = false
  map.setDestination(null)
  map.setStops([])
  map.setRoute(null)
  $('c-route').hidden = true
  $('btn-route').textContent = 'Plan route'
  if (state.map === 'route') {
    state.map = 'explore'
    map.setMode('explore')
    $('coords').hidden = true
    instruction(null)
  }
  clearBar()
}

// ---------------- Destination by coordinates ----------------
function msg(text) {
  $('coords-msg').hidden = !text
  $('coords-msg').textContent = text || ''
}

function readCoords() {
  const lat = parseFloat($('lat').value)
  let lon = parseFloat($('lon').value)
  const latOk = Number.isFinite(lat) && lat >= -90 && lat <= 90
  const lonOk = Number.isFinite(lon)
  $('lat').setAttribute('aria-invalid', !latOk)
  $('lon').setAttribute('aria-invalid', !lonOk)
  if (!latOk || !lonOk) return null
  if (lon < 0) { lon += 360; $('lon').value = lon.toFixed(6) }
  return { lat, lon }
}

let bbox = null // boxwork window (/map): warning when the destination falls outside
fetch('/map').then((r) => r.json()).then((m) => (bbox = m.window || null)).catch(() => {})

$('coords').addEventListener('submit', (e) => {
  e.preventDefault()
  const c = readCoords()
  if (!c) return msg('Latitude between −90 and 90; numeric longitude (°E).')
  const inside = !bbox || (c.lat >= bbox.lat_min && c.lat <= bbox.lat_max && c.lon >= bbox.lon_min && c.lon <= bbox.lon_max)
  msg(inside ? null : 'Outside the boxwork window — results may be empty.')
  setDestination(c)
  map.center(c)
})

// ---------------- Click on the expanded map ----------------
let readoutSeq = 0
async function mapClick(lat, lon) {
  const p = { lat, lon }
  if (state.map === 'route') {
    if (awaitingPosition) return markPosition(lat, lon)
    if (awaitingStop) {
      awaitingStop = false
      instruction(null)
      state.stops.push(p)
      map.setStops(state.stops)
      return updateRoute(state.position, state.destination, state.stops)
    }
    $('lat').value = lat.toFixed(6)
    $('lon').value = lon.toFixed(6)
    msg(null)
    return setDestination(p)
  }
  return readPoint(lat, lon) // explore: quick readout of lat, lon and elevation
}

/** "📍 I am here" (click or voice): the followed route does not change, only where the new options start from. */
function markPosition(lat, lon) {
  awaitingPosition = false
  instruction(null)
  state.position = { lat, lon, label: 'the marked position', source: 'marked on the map', kind: 'position' }
  map.setOrigin(state.position)
}

/** Writes (and returns) lat, lon and elevation of the point in the readout line. */
async function readPoint(lat, lon) {
  const mine = ++readoutSeq
  const el = $('readout')
  el.hidden = false
  el.textContent = `${lat.toFixed(6)}° · ${lon.toFixed(6)}°E · querying elevation…`
  try {
    const point = await getPoint(lat, lon)
    const rv = point.raster_values
    const ti = point.thermal_inertia
    if (mine !== readoutSeq) return
    el.textContent = `${lat.toFixed(6)}° · ${lon.toFixed(6)}°E · ` + (rv.elevation_m === null
      ? 'no elevation (outside the DTM)'
      : `${rv.elevation_m.toFixed(1)} m${rv.slope_deg !== null ? ` · ${rv.slope_deg.toFixed(1)}°` : ''}`)
      + (ti ? ` · TI ${ti.value}` : '')
  } catch (e) {
    if (mine === readoutSeq) el.textContent = `${lat.toFixed(6)}° · ${lon.toFixed(6)}°E · ${e.message}`
  }
  return el.textContent
}

// ---------------- Layers (delegation: the HTML is rebuilt on every render) ----------------
$('layers-panel').addEventListener('click', (e) => {
  const go = e.target.closest('[data-insol-go]')?.dataset.insolGo
  if (go !== undefined) {
    state.insolation.hour = quarter(Number(go))
    updateInsolation()
    return
  }
  const id = e.target.closest('[data-toggle]')?.dataset.toggle
  if (!id) return
  const c = state.layers[id]
  c.visible = !c.visible
  map.setLayerVisible(id, c.visible)
  if (id === 'insolation' && c.visible) startInsolation()
  layers()
})
/** First time the sun layer turns on: starts at the arrival hour (if there is a route) or the current one. */
function startInsolation() {
  if (state.insolation.started) return
  const h = arrivalHour(state) ?? state.clock?.ltst
  if (h !== undefined) state.insolation.hour = quarter(h)
  state.insolation.started = true
  updateInsolation()
}
// insolation hour: 'change' (slider release), not 'input' -- each hour is a new grid on the server
// with a destination set, the query already tells whether IT is in sun or shade at the chosen hour
function updateInsolation() {
  const { hour } = state.insolation
  map.setInsolationHour(hour)
  getInsolation(hour, state.destination)
    .catch(() => getInsolation(hour)) // destination outside the 1 m DTM: Sun position only
    .then((info) => { state.insolation.info = info; layers() })
    .catch(() => { state.insolation.info = null; layers() })
}
const quarter = (h) => Math.round(h * 4) / 4

// simulated clock: refreshes every minute (solar time advances ~1 min per minute)
function readClock() {
  getClock()
    .then((r) => {
      state.clock = r
      if (state.layers.insolation.visible) layers()
    })
    .catch(() => {})
}
readClock()
setInterval(readClock, 60_000)
$('layers-panel').addEventListener('change', (e) => {
  if (e.target.matches('[data-insol-hour]')) {
    state.insolation.hour = Number(e.target.value)
    updateInsolation()
    return
  }
})
// Custom atmospheric variable selector (replaces the native <select>)
const closeAtmMenu = () => {
  const m = $('layers-panel').querySelector('.lyr-menu')
  if (!m || m.hidden) return
  m.hidden = true
  m.parentElement.querySelector('[data-atm-open]').setAttribute('aria-expanded', 'false')
}
$('layers-panel').addEventListener('click', (e) => {
  const btn = e.target.closest('[data-atm-open]')
  if (btn) {
    const m = btn.parentElement.querySelector('.lyr-menu')
    const open = m.hidden
    closeAtmMenu()
    m.hidden = !open
    btn.setAttribute('aria-expanded', String(open))
    return
  }
  const opt = e.target.closest('[data-atm-var]')
  if (!opt) return
  state.atmosphere.variable = opt.dataset.atmVar
  map.setAtmosphere(state.atmosphere.geo, state.atmosphere.variable, state.layers.atmosphere_track.visible)
  layers()
})
document.addEventListener('click', (e) => { if (!e.target.closest('.lyr-sel')) closeAtmMenu() })

// ---------------- Keyboard ----------------
function back() {
  const atmMenu = $('layers-panel').querySelector('.lyr-menu')
  if (atmMenu && !atmMenu.hidden) return closeAtmMenu()
  if (document.body.classList.contains('viewer-front')) closeViewer()
  else if (state.map !== 'viewer') closeMap()
  else closeViewer()
}
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape' || !$('assistant').hidden) return // the assistant handles its own Esc
  back()
})

// ---------------- F08: assistant ----------------
/** Route requested by voice or planned by the agent: opens the map in route mode, like the
 * "Plan route" button -- only setting the destination left the route hidden in the viewer minimap. */
function openRouteTo(destination) {
  if (state.map !== 'route') openMap('route')
  state.routeActive = true
  return setDestination({ lat: destination.lat, lon: destination.lon })
}

/** Problem reported in the middle of the route: the card shows the new options; the flag goes to the end of the suggested one. */
function showReplanning(res, origin) {
  if (state.map !== 'route') openMap('route')
  state.routeActive = true
  $('c-route').hidden = false
  showOptions(res, origin)
}

const assistant = initAssistant($('assistant'), () => state.place ?? state.position, routeForAgent, openRouteTo, showReplanning,
  () => state.position, (item) => { answersShown++; answerCard.showAnswer(item) })

// ---------------- F08: voice ("Hey guide, route to …" or a spoken question) ----------------
// the route always starts at the current position (tracker); voice only chooses the destination
initVoice($('btn-voice'), $('voice-status'), {
  currentPoint: () => state.position,
  route: (_origin, destination) => openRouteTo(destination),
  ask: (text) => {
    return assistant.send(text) // the answer card opens by itself; the assistant history stays closed
  },
  execute,
  context,
})

// ---------------- F11: actions of each block (catalog in commands.json) ----------------
const activeViewer = () => viewerBg ?? viewer
const clickRoute = (sel) => { const b = $('c-route').querySelector(sel); if (!b) return false; b.click() }
/** Field of the route card that only reacts to 'change' (route.js). */
function fill(sel, value) {
  const i = $('c-route').querySelector(sel)
  if (!i) return 'That field only appears once the route is computed.'
  i.value = value
  i.dispatchEvent(new Event('change', { bubbles: true }))
}
function setLayer(layer, visible, opacity) {
  const c = state.layers[layer]
  c.visible = visible
  if (opacity !== undefined) { c.opacity = opacity; map.setLayerOpacity(layer, opacity) }
  map.setLayerVisible(layer, visible)
  if (layer === 'insolation' && visible) startInsolation()
  layers()
}
/** Voice: chosen hour turns the sun layer on (and wins over the automatic first hour). */
function setInsolationHour(h) {
  state.insolation.started = true
  state.insolation.hour = quarter(h)
  setLayer('insolation', true)
  updateInsolation()
}
register('m-A', {
  expand: () => { if (state.map !== 'viewer') return 'The map is already open.'; openMap('explore') },
  collapse: () => { if (state.map === 'viewer') return 'The map is already collapsed.'; closeMap() },
  zoom_in: ({ levels }) => { map.zoomBy(levels) },
  zoom_out: ({ levels }) => { map.zoomBy(-levels) },
  move: ({ direction }) => { map.pan(direction) },
  center: () => { map.center(state.destination ?? state.position, state.route) },
  read: async () => {
    const c = map.mapCenter()
    if (!c) return 'The map has not loaded yet.'
    if (state.map === 'viewer') openMap('explore')
    $('readout').hidden = false
    await readPoint(c.lat, c.lon) // the readout line shows lat, lon and elevation
  },
})
register('m-B', {
  show: ({ layer }) => setLayer(layer, true),
  hide: ({ layer }) => setLayer(layer, false),
  opacity: ({ layer, value }) => setLayer(layer, true, value / 100),
  hour: ({ hour }) => { setInsolationHour(hour) },
  hour_preset: ({ moment }) => {
    const h = moment === 'now' ? state.clock?.ltst : arrivalHour(state)
    if (h == null) return moment === 'now' ? 'The solar clock has not loaded yet.' : 'There is no route: no arrival hour.'
    setInsolationHour(h)
  },
  variable: ({ variable }) => {
    const { geo, error } = state.atmosphere
    if (!geo) return error ? `No atmospheric data: ${error}` : 'The atmospheric data is still loading.'
    state.atmosphere.variable = variable
    map.setAtmosphere(geo, variable, true)
    setLayer('atmosphere_track', true)
  },
})
register('m-C', {
  plan: () => { openMap('route') },
  type: ({ type }) => clickRoute(`[data-type="${type}"]`),
  sol: ({ delta }) => clickRoute(`[data-sol-step="${delta}"]`),
  target: () => clickRoute('[data-action="target"]'),
  next: () => changePage($('c-route'), 1) || 'Route: already on the last page.',
  previous: () => changePage($('c-route'), -1) || 'Route: already on the first page.',
  collapse: () => { collapseGroup('g-route', true) },
  expand: () => { collapseGroup('g-route', false) },
  cancel: () => { if (!state.routeActive) return 'There is no route.'; cancelRoute() },
  destination_center: () => {
    const c = map.mapCenter()
    if (!c) return 'The map has not loaded yet.'
    if (state.map !== 'route') openMap('route')
    $('lat').value = c.lat.toFixed(6)
    $('lon').value = c.lon.toFixed(6)
    setDestination(c)
  },
  here: () => {
    const c = map.mapCenter()
    if (!c) return 'The map has not loaded yet.'
    markPosition(c.lat, c.lon)
  },
  stop: () => {
    const c = map.mapCenter()
    if (!state.destination) return 'Set the destination before the stop.'
    if (!c) return 'The map has not loaded yet.'
    state.stops.push(c)
    map.setStops(state.stops)
    updateRoute(state.position, state.destination, state.stops)
  },
  remove_stop: ({ n }) => {
    if (!state.stops[n - 1]) return `There is no stop ${n}.`
    state.stops.splice(n - 1, 1)
    map.setStops(state.stops)
    updateRoute(state.position, state.destination, state.stops)
  },
  go_sol: ({ sol }) => fill('[data-sol-eva]', sol),
  o2: ({ liters }) => fill('[data-field="o2-capacity"]', liters),
  measurement: ({ sol, minimum, maximum, pressure, dose }) => {
    const f = $('c-route').querySelector('form[data-measure]')
    if (!f) return 'Open a route with the forecast loaded to record the measurement.'
    Object.entries({ sol: Math.round(sol), temp_min_c: minimum, temp_max_c: maximum, pressure_pa: pressure, dose_ugy_day: dose ?? '' })
      .forEach(([k, v]) => { f.elements[k].value = v })
    f.requestSubmit()
  },
  delete_measurement: () => clickRoute('[data-delete-measurement]'),
})
register('m-D', {
  expand: () => { if (!viewer) return 'No panorama here.'; if (!inViewer) expand() },
  collapse: () => { if (!inViewer) return 'The panorama is not in the viewer.'; collapse() },
  rotate: ({ direction, degrees }) => {
    const v = activeViewer()
    if (!v) return 'No panorama here.'
    if (direction === 'left' || direction === 'right') v.setYaw(v.getYaw() + (direction === 'right' ? degrees : -degrees))
    else v.setPitch(v.getPitch() + (direction === 'up' ? degrees : -degrees))
  },
  zoom_in: () => { const v = activeViewer(); if (!v) return 'No panorama here.'; v.setHfov(v.getHfov() - 15) },
  zoom_out: () => { const v = activeViewer(); if (!v) return 'No panorama here.'; v.setHfov(v.getHfov() + 15) },
  center: () => { const v = activeViewer(); if (!v) return 'No panorama here.'; v.setYaw(pointYaw) },
})
register('m-E', {
  open: ({ n }) => {
    const ph = photoList[photoPage * PHOTOS_PER_PAGE + n - 1]
    if (!ph) return `There is no photo ${n} on this page.`
    openPhoto(ph)
  },
  next: () => {
    if ((photoPage + 1) * PHOTOS_PER_PAGE >= photoList.length) return 'Photos: already on the last page.'
    photoPage++; renderPhotos(1)
  },
  previous: () => {
    if (photoPage === 0) return 'Photos: already on the first page.'
    photoPage--; renderPhotos(-1)
  },
  collapse: () => { collapseGroup('g-images', true) },
  expand: () => { collapseGroup('g-images', false) },
})
register('m-F', {
  open: () => { if ($('c-answer').hidden) return 'No answer card open.'; $('c-answer').open = true },
  close: () => { $('c-answer').open = false },
  next: () => changePage($('answer'), 1) || 'Answer card: already on the last page.',
  previous: () => changePage($('answer'), -1) || 'Answer card: already on the first page.',
  science: () => {
    const b = $('c-answer').querySelector('[data-science]')
    if ($('c-answer').hidden || !b) return 'The answer has no science details.'
    b.click()
  },
})
register('m-G', {
  open: () => { assistant.open(true) },
  close: () => { assistant.open(false) },
  next: () => changePage($('assistant'), 1) || 'Assistant: there is no older answer.',
  previous: () => changePage($('assistant'), -1) || 'Assistant: already on the newest.',
})
register('m-H', {
  close: () => { if ($('viewer-close').hidden) return 'The viewer is already empty.'; closeViewer() },
})
register('m-I', {
  set: ({ lat, lon }) => {
    if (state.map !== 'route') openMap('route')
    $('lat').value = lat
    $('lon').value = lon
    $('coords').requestSubmit()
  },
})
register('m-J', {
  read: () => ($('c-status').hidden ? 'There is no warning.' : { ok: true, text: $('c-status').textContent.trim() }),
})
register('sys', {
  back: () => { if (!$('assistant').hidden) assistant.open(false); else back() },
  microphone: () => { if ($('btn-voice').getAttribute('aria-pressed') !== 'true') return 'The microphone is already off.'; $('btn-voice').click() },
  help: () => ({ ok: true, text: describeOpen() }),
})
initCommands().catch((e) => console.warn('command catalog unavailable:', e))

// ---------------- Initial load ----------------
getPosition()
  .then((p) => {
    state.position = { lat: p.lat, lon: p.lon, label: 'the current position', source: p.label, kind: 'position' }
    map.setOrigin(state.position)
    map.center(state.position)
  })
  .catch((e) => card('c-status', `<p class="empty error">No position: ${esc(e.message)}</p>`))

getConditions().then(renderConditions).catch(() => {}) // no cached sol yet: stay quiet, not an error worth a banner

try {
  const metas = await getLayers()
  $('map-status').remove()
  map.createMap($('map'), metas, {
    onClick: mapClick,
    onClose: closeMap,
    onLoad: () => {
      if (state.route) map.setRoute(state.route) // route computed before the map loaded
      updateRoute.redraw()
      if (state.position) { map.setOrigin(state.position); map.center(state.position) }
      getAtmosphereTrack()
        .then((geo) => {
          state.atmosphere.geo = geo
          map.setAtmosphere(geo, state.atmosphere.variable, state.layers.atmosphere_track.visible)
          layers()
        })
        .catch((e) => { state.atmosphere.error = e.message; layers() })
    },
  })
} catch (e) {
  $('map-status').textContent = `no map: ${e.message}`
}
