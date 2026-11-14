// Mapa MapLibre (antes MapCanvas.tsx + style.ts). API imperativa direta:
// app.js chama as funções exportadas quando o estado muda.
import { Map, Marker, NavigationControl } from './lib/maplibre/maplibre-gl.mjs'
import { getRoverTrack } from './api.js'
import { LAYER_MAXZOOM, SLOPE_COLOR_HEX, TOGGLEABLE_LAYERS } from './layers.js'

/** Centro da campanha de boxwork (sol ~4500-4684, MSL_waypoints.json) --
 * só fallback de câmera; o bbox real de cada camada vem de /layers. */
const CENTRO_INICIAL = [137.384, -4.801]
const ZOOM_INICIAL = 15 // começa no nível da HiRISE

const ROUTE_ID = 'h2g2-route-line'
const PHOTOS_ID = 'h2g2-rover-photos'
const TRACK_LINE_ID = 'rover_track_line'
const TRACK_STOPS_ID = 'rover_track_stops'

const corPorStatus = (padrao) => [
  'match', ['get', 'slope_status'],
  'atencao', SLOPE_COLOR_HEX.atencao,
  'perigo', SLOPE_COLOR_HEX.perigo,
  padrao,
]

/** União dos bboxes + 10% de folga -- vira maxBounds, pra não cair no vazio
 * fora da área com dado baixado. */
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

/** Zoom mínimo pra cobertura das camadas base (CTX/HiRISE, não THEMIS que é
 * bem mais larga) preencher o viewport -- maxBounds só trava o pan.
 * Mesma conta de tile 256px do api/tile_server.py. */
export function minZoomToCover([[minLon, minLat], [maxLon, maxLat]], w, h) {
  return Math.max(Math.log2((w * 360) / (256 * (maxLon - minLon))), Math.log2((h * 360) / (256 * (maxLat - minLat))))
}

function buildStyle(metas) {
  const porNome = Object.fromEntries(metas.map((m) => [m.layer_name, m]))
  const sources = {}
  const layers = [{ id: 'background', type: 'background', paint: { 'background-color': '#05070a' } }]
  for (const l of TOGGLEABLE_LAYERS) {
    if (!porNome[l.id]) continue // camada ainda não populada no backend
    sources[l.id] = {
      type: 'raster',
      // MapLibre exige URL absoluta pro template de tile
      tiles: [`${location.origin}/tiles/${l.id}/{z}/{x}/{y}.png`],
      tileSize: 256,
      minzoom: 0,
      maxzoom: LAYER_MAXZOOM[l.id] ?? 18,
    }
    layers.push({
      id: l.id,
      type: 'raster',
      source: l.id,
      layout: { visibility: l.defaultVisible ? 'visible' : 'none' },
      paint: { 'raster-opacity': l.defaultOpacity },
      // overlay some além da resolução real em vez de lavar a HiRISE por baixo
      ...(l.grupo === 'overlay' ? { maxzoom: LAYER_MAXZOOM[l.id] } : {}),
    })
  }
  return { version: 8, sources, layers }
}

let map = null
let carregado = false
let modo = 'point'
let trilhaVisivel = false
let marcadorClique, marcadorOrigem, marcadorDestino

function marcador(classe, filho) {
  const el = document.createElement('div')
  el.className = classe
  if (filho) el.appendChild(filho)
  return new Marker({ element: el })
}

const vazio = () => ({ type: 'FeatureCollection', features: [] })

/** Cria o mapa. callbacks: onClick(lat, lon), onPhotoClick(props), onZoom(z), onLoad(). */
export function criarMapa(container, metas, { onClick, onPhotoClick, onZoom, onLoad }) {
  const bounds = dataBounds(metas)
  const base = new Set(TOGGLEABLE_LAYERS.filter((l) => l.grupo === 'base').map((l) => l.id))
  const baseBounds = dataBounds(metas.filter((m) => base.has(m.layer_name)))
  const rect = container.getBoundingClientRect()

  map = new Map({
    container,
    style: buildStyle(metas),
    center: CENTRO_INICIAL,
    zoom: ZOOM_INICIAL,
    maxBounds: bounds ?? undefined,
    minZoom: baseBounds ? minZoomToCover(baseBounds, rect.width, rect.height) : undefined,
    attributionControl: false,
  })
  map.addControl(new NavigationControl({ showCompass: false }), 'bottom-right')

  const dot = document.createElement('div')
  dot.className = 'h2g2-crosshair-dot'
  marcadorClique = marcador('h2g2-crosshair', dot)
  marcadorOrigem = marcador('h2g2-route-marker h2g2-route-marker--origin')
  marcadorDestino = marcador('h2g2-route-marker h2g2-route-marker--destination')

  map.on('click', (e) => {
    // pin de foto consome o clique (não abre briefing nem marca rota por baixo)
    const foto = carregado && map.queryRenderedFeatures(e.point, { layers: [PHOTOS_ID] })[0]
    if (foto) return onPhotoClick(foto.properties)
    if (modo === 'point') marcadorClique.setLngLat(e.lngLat).addTo(map)
    onClick(e.lngLat.lat, e.lngLat.lng)
  })

  // `zoom` dispara dezenas de vezes por segundo -- throttle ~8/s; zoomend garante o valor final
  let ultimo = 0
  map.on('zoom', () => {
    const agora = performance.now()
    if (agora - ultimo > 120) {
      ultimo = agora
      onZoom(map.getZoom())
    }
  })
  map.on('zoomend', () => onZoom(map.getZoom()))

  map.on('load', () => {
    map.addSource(ROUTE_ID, { type: 'geojson', data: vazio() })
    map.addLayer({
      id: ROUTE_ID,
      type: 'line',
      source: ROUTE_ID,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-width': 4, 'line-color': corPorStatus(SLOPE_COLOR_HEX.seguro) },
    })
    map.addSource(PHOTOS_ID, { type: 'geojson', data: vazio() })
    map.addLayer({
      id: PHOTOS_ID,
      type: 'circle',
      source: PHOTOS_ID,
      paint: { 'circle-radius': 5, 'circle-color': '#f2b33d', 'circle-stroke-width': 1.5, 'circle-stroke-color': '#0a0a0b' },
    })
    map.on('mouseenter', PHOTOS_ID, () => (map.getCanvas().style.cursor = 'pointer'))
    map.on('mouseleave', PHOTOS_ID, () => (map.getCanvas().style.cursor = modo === 'point' ? '' : 'crosshair'))

    carregado = true
    onZoom(map.getZoom())
    onLoad()

    // trilha do Curiosity (feature 08) -- falha silenciosa, o mapa segue útil sem ela
    getRoverTrack().then(adicionarTrilha).catch(() => {})
  })
}

/** Paradas reais do Curiosity coloridas pela inclinação medida pelo rover
 * (mesmos limites do DTM). Entra desligada, como Relevo/THEMIS. */
function adicionarTrilha(paradas) {
  map.addSource('rover_track', {
    type: 'geojson',
    data: {
      type: 'FeatureCollection',
      features: [
        { type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: paradas.map((s) => [s.lon, s.lat]) } },
        ...paradas.map((s) => ({
          type: 'Feature',
          properties: { slope_status: s.status, tilt: s.tilt, sol: s.sol },
          geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
        })),
      ],
    },
  })
  const visibility = trilhaVisivel ? 'visible' : 'none'
  map.addLayer({
    id: TRACK_LINE_ID,
    type: 'line',
    source: 'rover_track',
    filter: ['==', ['geometry-type'], 'LineString'],
    layout: { visibility },
    paint: { 'line-color': '#ffffff', 'line-opacity': 0.35, 'line-width': 1 },
  })
  map.addLayer({
    id: TRACK_STOPS_ID,
    type: 'circle',
    source: 'rover_track',
    filter: ['==', ['geometry-type'], 'Point'],
    layout: { visibility },
    paint: {
      'circle-radius': ['match', ['get', 'slope_status'], 'seguro', 3, 6],
      'circle-color': corPorStatus(SLOPE_COLOR_HEX.seguro),
      'circle-stroke-color': '#05070a',
      'circle-stroke-width': 1,
    },
  })
}

export function setCamadaVisivel(id, visivel) {
  map?.setLayoutProperty(id, 'visibility', visivel ? 'visible' : 'none')
}

export function setCamadaOpacidade(id, opacidade) {
  map?.setPaintProperty(id, 'raster-opacity', opacidade)
}

/** 'point' | 'pick-origin' | 'pick-destination' -- cursor vira mira no modo rota. */
export function setModo(novo) {
  modo = novo
  if (!map) return
  map.getCanvas().style.cursor = modo === 'point' ? '' : 'crosshair'
  // crosshair antigo do "último ponto" confundia a leitura da rota
  if (modo !== 'point') marcadorClique.remove()
}

export function limparPonto() {
  marcadorClique?.remove()
}

function posicionar(m, p) {
  if (!map) return
  if (p) m.setLngLat([p.lon, p.lat]).addTo(map)
  else m.remove()
}
export const setOrigem = (p) => posicionar(marcadorOrigem, p)
export const setDestino = (p) => posicionar(marcadorDestino, p)

export function setRota(rota) {
  if (!carregado) return
  map.getSource(ROUTE_ID).setData({
    type: 'FeatureCollection',
    features: (rota?.trechos_risco ?? []).map((t) => ({
      type: 'Feature',
      properties: { slope_status: t.slope_status },
      geometry: { type: 'LineString', coordinates: [[t.de[1], t.de[0]], [t.para[1], t.para[0]]] },
    })),
  })
}

export function setFotos(fotos) {
  if (!carregado) return
  map.getSource(PHOTOS_ID).setData({
    type: 'FeatureCollection',
    features: fotos.map((p) => ({
      type: 'Feature',
      properties: { lat: p.lat, lon: p.lon, sol: p.sol, camera: p.camera, url: p.url },
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
    })),
  })
}

export function setFotosVisiveis(visivel) {
  if (carregado) setCamadaVisivel(PHOTOS_ID, visivel)
}

export function setTrilhaVisivel(visivel) {
  trilhaVisivel = visivel
  if (!map?.getLayer(TRACK_LINE_ID)) return
  setCamadaVisivel(TRACK_LINE_ID, visivel)
  setCamadaVisivel(TRACK_STOPS_ID, visivel)
}
