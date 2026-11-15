// MapLibre map (formerly MapCanvas.tsx + style.ts). Direct imperative API:
// app.js calls the exported functions when the state changes.
import { Map, Marker, NavigationControl, Popup } from './lib/maplibre/maplibre-gl.mjs'
import { CONTINUOUS_SCALE, LAYER_MAXZOOM, SLOPE_COLOR_HEX, TOGGLEABLE_LAYERS } from './layers.js'

/** Center of the boxwork campaign (sol ~4500-4684, MSL_waypoints.json) --
 * camera fallback only; the real bbox of each layer comes from /layers. */
const INITIAL_CENTER = [137.384, -4.801]
const INITIAL_ZOOM = 15 // starts at HiRISE level

const ROUTE_ID = 'h2g2-route-line'
const ROUTE_ALT_ID = 'h2g2-route-alt' // the other variants: dashed, under the active one

const colorByStatus = (fallback) => [
  'match', ['get', 'slope_status'],
  'caution', SLOPE_COLOR_HEX.caution,
  'danger', SLOPE_COLOR_HEX.danger,
  fallback,
]

/** Union of the bboxes + 10% margin -- becomes maxBounds, so you don't fall into the void
 * outside the area with downloaded data. */
export function dataBounds(metas) {
  if (metas.length === 0) return null
  const minLon = Math.min(...metas.map((m) => m.min_lon))
  const minLat = Math.min(...metas.map((m) => m.min_lat))
  const maxLon = Math.max(...metas.map((m) => m.max_lon))
  const maxLat = Math.max(...metas.map((m) => m.max_lat))
  const padLon = (maxLon - minLon) * 0.1
  const padLat = (maxLat - minLat) * 0.1
  return [[minLon - padLon, minLat - padLat], [maxLon + padLon, maxLat + padLat]]
}

/** Minimum zoom so the base layers' coverage (CTX/HiRISE, not THEMIS which is
 * much wider) fills the viewport -- maxBounds only locks panning.
 * Same 256px tile math as api/tile_server.py. */
export function minZoomToCover([[minLon, minLat], [maxLon, maxLat]], w, h) {
  return Math.max(Math.log2((w * 360) / (256 * (maxLon - minLon))), Math.log2((h * 360) / (256 * (maxLat - minLat))))
}

// insolation: the solar hour goes in the tile URL (each hour is a different grid on the server)
let insolationHour = 9
const tileUrl = (id) => `${location.origin}/tiles/${id}/{z}/{x}/{y}.png${id === 'insolation' ? `?hour=${insolationHour}` : ''}`

export function setInsolationHour(hour) {
  insolationHour = hour
  map?.getSource('insolation')?.setTiles([tileUrl('insolation')])
}

function buildStyle(metas) {
  const byName = Object.fromEntries(metas.map((m) => [m.layer_name, m]))
  const sources = {}
  const layers = [{ id: 'background', type: 'background', paint: { 'background-color': '#05070a' } }]
  for (const l of TOGGLEABLE_LAYERS) {
    if (l.kind === 'points' || !byName[l.id]) continue // points: map.js separately; or layer not populated yet
    sources[l.id] = {
      type: 'raster',
      // MapLibre requires an absolute URL for the tile template
      tiles: [tileUrl(l.id)],
      tileSize: 256,
      minzoom: 0,
      maxzoom: LAYER_MAXZOOM[l.id] ?? 18,
    }
    layers.push({
      id: l.id,
      type: 'raster',
      source: l.id,
      layout: { visibility: l.defaultVisible ? 'visible' : 'none' },
      paint: { 'raster-opacity': l.defaultOpacity, ...(l.id === 'themis_ti' ? { 'raster-resampling': 'nearest' } : {}) },
      // no maxzoom on the layer: the source's (LAYER_MAXZOOM) makes MapLibre upscale the last level
    })
  }
  return { version: 8, sources, layers }
}

let map = null
let loaded = false
let mode = 'viewer' // 'viewer' (circle) | 'explore' | 'route'
let clickMarker, originMarker, destinationMarker, panoMarker

function marker(className, child, options = {}) {
  const el = document.createElement('div')
  el.className = className
  if (typeof child === 'string') el.innerHTML = child
  else if (child) el.appendChild(child)
  return new Marker({ element: el, ...options })
}

// finish flag: the base of the pole (x=3, y=27) lands exactly on the destination
const FLAG = `<svg viewBox="0 0 24 28" width="24" height="28" aria-hidden="true">
  <path d="M3 27V2" stroke="#0a0a0b" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M3 27V2" stroke="#e2e2e6" stroke-width="1.6" stroke-linecap="round"/>
  <path d="M4 2.5h16l-4 5 4 5H4z" fill="#E8643F" stroke="#0a0a0b" stroke-width="1.2" stroke-linejoin="round"/>
</svg>`

const empty = () => ({ type: 'FeatureCollection', features: [] })

// ✕ button to close the expanded map: sits right below the zoom controls (same group)
let onCloseCb = () => {}
const CloseControl = {
  onAdd() {
    const group = document.createElement('div')
    group.className = 'maplibregl-ctrl maplibregl-ctrl-group'
    const b = document.createElement('button')
    b.type = 'button'
    b.className = 'h2g2-close-map'
    b.title = 'Close map (Esc)'
    b.setAttribute('aria-label', 'Close map')
    b.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M5 5l14 14M19 5L5 19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
    // stopPropagation: otherwise the click reaches #map-box, which reopens the map right after closing
    b.addEventListener('click', (e) => { e.stopPropagation(); onCloseCb() })
    group.appendChild(b)
    this._group = group
    return group
  },
  onRemove() { this._group.remove() },
}

/** Creates the map. callbacks: onClick(lat, lon), onLoad(), onClose(). */
export function createMap(container, metas, { onClick, onLoad, onClose }) {
  onCloseCb = onClose ?? (() => {})
  const bounds = dataBounds(metas)
  const base = new Set(TOGGLEABLE_LAYERS.filter((l) => l.group === 'base').map((l) => l.id))
  const baseBounds = dataBounds(metas.filter((m) => base.has(m.layer_name)))
  const rect = container.getBoundingClientRect()

  map = new Map({
    container,
    style: buildStyle(metas),
    center: INITIAL_CENTER,
    zoom: INITIAL_ZOOM,
    maxBounds: bounds ?? undefined,
    minZoom: baseBounds ? minZoomToCover(baseBounds, rect.width, rect.height) : undefined,
    attributionControl: false,
  })
  // the bottom one goes first: in the bottom strip the last one added sits on top
  map.addControl(CloseControl, 'bottom-left')
  map.addControl(new NavigationControl({ showCompass: false }), 'bottom-left')

  const dot = document.createElement('div')
  dot.className = 'h2g2-crosshair-dot'
  clickMarker = marker('h2g2-crosshair', dot)
  panoMarker = marker('h2g2-pano-marker') // created first: sits below the others
  originMarker = marker('h2g2-route-marker h2g2-route-marker--origin')
  originMarker.getElement().title = 'Current position (start of the traverse)'
  destinationMarker = marker('h2g2-flag', FLAG, { anchor: 'bottom-left', offset: [-3, 1] })
  destinationMarker.getElement().title = 'Destination'

  map.on('click', (e) => {
    // a photo pin consumes the click (does not open briefing nor mark a route underneath)
    if (mode === 'viewer') return // minimized: the click only expands (app.js)
    if (mode === 'explore') clickMarker.setLngLat(e.lngLat).addTo(map)
    onClick(e.lngLat.lat, e.lngLat.lng)
  })

  map.on('load', () => {
    map.addSource(ROUTE_ALT_ID, { type: 'geojson', data: empty() })
    map.addLayer({
      id: ROUTE_ALT_ID,
      type: 'line',
      source: ROUTE_ALT_ID,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-width': 3, 'line-color': '#e2e2e6', 'line-opacity': 0.75, 'line-dasharray': [1.5, 2] },
    })
    map.addSource(ROUTE_ID, { type: 'geojson', data: empty() })
    map.addLayer({
      id: ROUTE_ID,
      type: 'line',
      source: ROUTE_ID,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      filter: ['!=', ['get', 'by_forecast'], true],
      paint: { 'line-width': 4, 'line-color': colorByStatus(SLOPE_COLOR_HEX.safe) },
    })
    // segments whose color changed only because of the rover forecast: dashed (legend explains)
    map.addLayer({
      id: `${ROUTE_ID}-prev`,
      type: 'line',
      source: ROUTE_ID,
      layout: { 'line-join': 'round' },
      filter: ['==', ['get', 'by_forecast'], true],
      paint: { 'line-width': 4, 'line-color': colorByStatus(SLOPE_COLOR_HEX.safe), 'line-dasharray': [1.5, 1.5] },
    })
    loaded = true
    onLoad()

  })
}

export const mapReady = () => loaded

export function setLayerVisible(id, visible) {
  if (!map?.getLayer(id)) return // points layer still without data
  map.setLayoutProperty(id, 'visibility', visible ? 'visible' : 'none')
}

export function setLayerOpacity(id, opacity) {
  map?.setPaintProperty(id, 'raster-opacity', opacity)
}

/** 'viewer' (circle) | 'explore' | 'route' -- cursor becomes a crosshair in route mode. */
export function setMode(next) {
  mode = next
  if (!map) return
  map.getCanvas().style.cursor = mode === 'route' ? 'crosshair' : ''
  if (mode !== 'explore') clickMarker.remove()
}

/** After the container changes size (circle <-> full screen). */
export function resize() {
  map?.resize()
}

/** Centers on the point or, with a route, frames the whole route. */
export function center(p, route = null) {
  if (!map) return
  const coords = (route?.risk_segments ?? []).flatMap((t) => [[t.from[1], t.from[0]], [t.to[1], t.to[0]]])
  if (coords.length) {
    const lons = coords.map((c) => c[0]), lats = coords.map((c) => c[1])
    map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 24, duration: 0, maxZoom: 18 })
  } else if (p) map.jumpTo({ center: [p.lon, p.lat], zoom: Math.max(map.getZoom(), 16) })
}

export function clearPoint() {
  clickMarker?.remove()
}

function place(m, p) {
  if (!map) return
  if (p) m.setLngLat([p.lon, p.lat]).addTo(map)
  else m.remove()
}
export const setOrigin = (p) => place(originMarker, p)
export const setDestination = (p) => place(destinationMarker, p)
/** Curiosity stop where the panorama shown in the bar was taken (null removes it). */
export function setPanorama(p) {
  place(panoMarker, p)
  if (p && panoMarker) panoMarker.getElement().title = `Nearest panorama · sol ${p.sol}`
}

let stopMarkers = []
/** Intermediate route stops. The count varies,
 * so the markers are recreated on each call instead of reusing a fixed one. */
export function setStops(stops) {
  if (!map) return
  stopMarkers.forEach((m) => m.remove())
  stopMarkers = stops.map((p) => marker('h2g2-route-marker h2g2-route-marker--stop').setLngLat([p.lon, p.lat]).addTo(map))
}

/** route: the active variant (color by slope); others: the remaining variants, dashed. */
export function setRoute(route, others = []) {
  if (!loaded) return
  map.getSource(ROUTE_ALT_ID).setData({
    type: 'FeatureCollection',
    features: others.map((r) => ({
      type: 'Feature',
      properties: { type: r.type },
      geometry: { type: 'LineString', coordinates: r.points.map(([lat, lon]) => [lon, lat]) },
    })),
  })
  map.getSource(ROUTE_ID).setData({
    type: 'FeatureCollection',
    features: (route?.risk_segments ?? []).map((t) => ({
      type: 'Feature',
      // feature 06: color includes the forecast; by_forecast marks the segment whose color differs from the map
      properties: { slope_status: t.predicted_status ?? t.slope_status, by_forecast: (t.predicted_status ?? t.slope_status) !== t.slope_status },
      geometry: { type: 'LineString', coordinates: [[t.from[1], t.from[0]], [t.to[1], t.to[0]]] },
    })),
  })
}

// ---------------- Atmospheric layer (REMS points along the traverse) ----------------
const ATM_ID = 'atmosphere_track'
let atmPopup = null

/** [min, max] range of the variable among the points with data, or null. */
export function atmosphereRange(geo, variable) {
  const v = geo.features.map((f) => f.properties[variable]).filter((x) => x !== null && x !== undefined)
  return v.length ? [Math.min(...v), Math.max(...v)] : null
}

function atmosphereColor(geo, variable) {
  const range = atmosphereRange(geo, variable)
  if (!range) return '#6b6b73'
  const [a, b] = range[0] === range[1] ? [range[0] - 1, range[1] + 1] : range
  const step = (b - a) / (CONTINUOUS_SCALE.length - 1)
  return ['case', ['==', ['get', variable], null], '#6b6b73',
    ['interpolate', ['linear'], ['get', variable], ...CONTINUOUS_SCALE.flatMap((c, i) => [a + i * step, c])]]
}

const fmt = (v, u) => (v === null || v === undefined ? 'no data' : `${Math.round(v * 10) / 10} ${u}`)

function popupHtml(p, geo) {
  const lines = Object.entries(geo.variables).map(([k, { label, unit }]) => `<div>${label}: <b>${fmt(p[k], unit)}</b></div>`).join('')
  const head = `<div><b>Sol ${p.sol}</b> · ${p.earth_date}${p.ls !== null ? ` · Ls ${p.ls}°` : ''}</div>`
  const footer = p.reason ? `<div class="atm-pop-note">${p.reason}</div>` : '<div class="atm-pop-note">REMS (PDS), measured · position = last stop of the sol</div>'
  return head + (p.reason ? '' : lines) + footer
}

/** Creates or updates the points layer. visible: toggle state. */
export function setAtmosphere(geo, variable, visible) {
  if (!loaded || !geo) return
  if (!map.getSource(ATM_ID)) {
    map.addSource(ATM_ID, { type: 'geojson', data: geo })
    // below the route: the route is what the astronaut follows
    map.addLayer({
      id: ATM_ID,
      type: 'circle',
      source: ATM_ID,
      layout: { visibility: visible ? 'visible' : 'none' },
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 13, 3, 17, 7],
        'circle-stroke-width': 1,
        'circle-stroke-color': 'rgba(0,0,0,.6)',
        'circle-opacity': ['case', ['==', ['get', variable], null], 0.45, 0.95],
      },
    }, ROUTE_ID)
    atmPopup = new Popup({ closeButton: false, closeOnClick: false, className: 'atm-pop', offset: 8 })
    map.on('mouseenter', ATM_ID, (e) => {
      map.getCanvas().style.cursor = 'help'
      atmPopup.setLngLat(e.features[0].geometry.coordinates).setHTML(popupHtml(e.features[0].properties, geo)).addTo(map)
    })
    map.on('mouseleave', ATM_ID, () => { map.getCanvas().style.cursor = ''; atmPopup.remove() })
  }
  map.setPaintProperty(ATM_ID, 'circle-color', atmosphereColor(geo, variable))
  map.setPaintProperty(ATM_ID, 'circle-opacity', ['case', ['==', ['get', variable], null], 0.45, 0.95])
}
