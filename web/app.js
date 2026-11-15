// H2G2 · front orchestration. Viewer (F03/F04) full screen; map (F01) in a circle
// that expands; route (F02 + F06) in a card; assistant (F08) at the top.
// The current position comes from the tracker (simulated at /api/position) and is the route origin.
import {
  getAtmosphereTrack, getScienceCard, getInsolation, getClock, getPhotosNear, getLayers, getPanorama,
  getPoint, getPosition,
} from './api.js'
import { TOGGLEABLE_LAYERS } from './layers.js'
import * as map from './map.js'
import { initAssistant } from './ui/agent.js'
import { arrivalHour, renderLayers } from './ui/layers-panel.js'
import { initRoute } from './ui/route.js'
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

// ---------------- Place (position or destination): status, panorama, photos, science card ----------------
let placeSeq = 0
let last = null // {pano} of the current place, to redraw the status

async function loadPlace(place) {
  const mine = ++placeSeq
  state.place = place
  loading()
  showScience('loading')
  const { lat, lon } = place
  const [pano, photos, science] = (await Promise.allSettled([
    getPanorama(lat, lon), getPhotosNear(lat, lon), getScienceCard(lat, lon),
  ])).map((r) => (r.status === 'fulfilled' ? r.value : null))
  if (mine !== placeSeq) return // another place already replaced this one
  last = { pano }
  map.setPanorama(pano?.found ? pano : null)
  if (pano) showPano(pano)
  else clearPano()
  showScience(science ?? 'error')
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
  for (const id of ['c-status', 'c-photos', 'c-science']) $(id).hidden = true
  collapseGroup('g-images', false)
}

const samePoint = (a, b) => a && b && a.lat === b.lat && a.lon === b.lon

function loading() {
  for (const id of ['c-pano', 'c-photos', 'c-science']) $(id).hidden = true
}

function card(id, html) { $(id).innerHTML = html; $(id).hidden = false }

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
  if (id === 'g-images') {
    $('science-cards').classList.toggle('collapsed', c)
    if (!c) requestAnimationFrame(() => { viewer?.resize(); placeScienceCards() }) // pannellum measured 0 px while hidden
  }
}
// science cards left of the images bar (bottom, CSS); on mobile they sit above the bottom sheet
function placeScienceCards() {
  const f = $('science-cards')
  f.style.bottom = mobile() ? innerHeight - $('floating').getBoundingClientRect().top + 8 + 'px' : ''
}
{
  const ro = new ResizeObserver(placeScienceCards)
  for (const id of ['floating', 'c-route', 'c-status', 'c-pano', 'c-photos']) ro.observe($(id))
  addEventListener('resize', placeScienceCards)
  $('floating').addEventListener('scroll', placeScienceCards)
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
  $('viewer-empty').hidden = true
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
  $('viewer-empty').hidden = !!viewer
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
  $('viewer-empty').hidden = true
  $('viewer-close').hidden = false
  viewerInFront(true)
}
// with the map expanded, the viewer (photo/panorama) overlays it; closing returns to the map
function viewerInFront(v) { document.body.classList.toggle('viewer-front', v) }
function closePhoto() {
  openedPhoto = null
  $('viewer-img').hidden = true
  $('viewer-img').removeAttribute('src')
  $('viewer-empty').hidden = inViewer
  $('viewer-close').hidden = !inViewer
}
function closeViewer() { if (inViewer) collapse(); closePhoto(); viewerInFront(false) }
$('viewer-close').addEventListener('click', closeViewer)

// ---------------- Science card (F04, science-card.js) ----------------
function showScience(d, open = false) {
  const wasOpen = $('c-science').open
  $('c-science').hidden = false
  $('c-science').open = open || (d !== 'loading' && wasOpen)
  const [name, type] = H2G2Card.title(d)
  $('science-name').textContent = name
  $('science-type').textContent = type
  $('science').innerHTML = H2G2Card.html(d)
  requestAnimationFrame(placeScienceCards)
}

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
  awaitingStop = false
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
  onActiveRoute: (r) => {
    state.route = r
    map.setRoute(r)
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
  onRemoveStop: (i) => {
    state.stops.splice(i, 1)
    map.setStops(state.stops)
    updateRoute(state.position, state.destination, state.stops)
  },
  onOpenTarget: async (target) => {
    if (!target?.lat) return
    if (state.map !== 'viewer') await closeMap()
    getScienceCard(target.lat, target.lon).then((f) => showScience(f, true), () => showScience('error', true))
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
  updateRoute(state.position, p, [])
}

function cancelRoute() {
  Object.assign(state, { routeActive: false, destination: null, stops: [], route: null })
  if (state.layers.insolation.visible) updateInsolation()
  awaitingStop = false
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
  // explore: quick readout of lat, lon and elevation
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
  if (id === 'insolation' && c.visible && !state.insolation.started) {
    // first time: starts at the arrival hour (if there is a route) or the current one
    const h = arrivalHour(state) ?? state.clock?.ltst
    if (h !== undefined) state.insolation.hour = quarter(h)
    state.insolation.started = true
    updateInsolation()
  }
  layers()
})
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
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape' || !$('assistant').hidden) return // the assistant handles its own Esc
  const atmMenu = $('layers-panel').querySelector('.lyr-menu')
  if (atmMenu && !atmMenu.hidden) return closeAtmMenu()
  if (document.body.classList.contains('viewer-front')) closeViewer()
  else if (state.map !== 'viewer') closeMap()
  else closeViewer()
})

// ---------------- F08: assistant ----------------
initAssistant($('assistant'), $('btn-assistant'), () => state.place ?? state.position)

// ---------------- Initial load ----------------
getPosition()
  .then((p) => {
    state.position = { lat: p.lat, lon: p.lon, label: 'the current position', source: p.label, kind: 'position' }
    map.setOrigin(state.position)
    map.center(state.position)
  })
  .catch((e) => card('c-status', `<p class="empty error">No position: ${esc(e.message)}</p>`))

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
