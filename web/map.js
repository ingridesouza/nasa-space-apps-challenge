// Mapa MapLibre (antes MapCanvas.tsx + style.ts). API imperativa direta:
// app.js chama as funções exportadas quando o estado muda.
import { Map, Marker, NavigationControl } from './lib/maplibre/maplibre-gl.mjs'
import { LAYER_MAXZOOM, SLOPE_COLOR_HEX, TOGGLEABLE_LAYERS } from './layers.js'

/** Centro da campanha de boxwork (sol ~4500-4684, MSL_waypoints.json) --
 * só fallback de câmera; o bbox real de cada camada vem de /layers. */
const CENTRO_INICIAL = [137.384, -4.801]
const ZOOM_INICIAL = 15 // começa no nível da HiRISE

const ROUTE_ID = 'h2g2-route-line'

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
let modo = 'visor' // 'visor' (círculo) | 'explorar' | 'rota'
let marcadorClique, marcadorOrigem, marcadorDestino, marcadorPano

function marcador(classe, filho, opcoes = {}) {
  const el = document.createElement('div')
  el.className = classe
  if (typeof filho === 'string') el.innerHTML = filho
  else if (filho) el.appendChild(filho)
  return new Marker({ element: el, ...opcoes })
}

// bandeira de chegada: a base do mastro (x=3, y=27) cai exatamente no destino
const BANDEIRA = `<svg viewBox="0 0 24 28" width="24" height="28" aria-hidden="true">
  <path d="M3 27V2" stroke="#0a0a0b" stroke-width="3.5" stroke-linecap="round"/>
  <path d="M3 27V2" stroke="#e2e2e6" stroke-width="1.6" stroke-linecap="round"/>
  <path d="M4 2.5h16l-4 5 4 5H4z" fill="#E8643F" stroke="#0a0a0b" stroke-width="1.2" stroke-linejoin="round"/>
</svg>`

const vazio = () => ({ type: 'FeatureCollection', features: [] })

// botão ✕ de fechar o mapa expandido: fica logo abaixo dos seletores de zoom (mesmo grupo)
let aoFechar = () => {}
const ControleFechar = {
  onAdd() {
    const grupo = document.createElement('div')
    grupo.className = 'maplibregl-ctrl maplibregl-ctrl-group'
    const b = document.createElement('button')
    b.type = 'button'
    b.className = 'h2g2-fechar-mapa'
    b.title = 'Fechar mapa (Esc)'
    b.setAttribute('aria-label', 'Fechar mapa')
    b.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M5 5l14 14M19 5L5 19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
    // stopPropagation: senão o clique chega ao #mapa-box, que reabre o mapa logo após fechar
    b.addEventListener('click', (e) => { e.stopPropagation(); aoFechar() })
    grupo.appendChild(b)
    this._grupo = grupo
    return grupo
  },
  onRemove() { this._grupo.remove() },
}

/** Cria o mapa. callbacks: onClick(lat, lon), onLoad(), onFechar(). */
export function criarMapa(container, metas, { onClick, onLoad, onFechar }) {
  aoFechar = onFechar ?? (() => {})
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
  // o de baixo entra primeiro: na faixa inferior o último adicionado fica em cima
  map.addControl(ControleFechar, 'bottom-left')
  map.addControl(new NavigationControl({ showCompass: false }), 'bottom-left')

  const dot = document.createElement('div')
  dot.className = 'h2g2-crosshair-dot'
  marcadorClique = marcador('h2g2-crosshair', dot)
  marcadorPano = marcador('h2g2-pano-marker') // criado antes: fica por baixo dos outros
  marcadorOrigem = marcador('h2g2-route-marker h2g2-route-marker--origin')
  marcadorOrigem.getElement().title = 'Posição atual (início do trajeto)'
  marcadorDestino = marcador('h2g2-flag', BANDEIRA, { anchor: 'bottom-left', offset: [-3, 1] })
  marcadorDestino.getElement().title = 'Destino'

  map.on('click', (e) => {
    // pin de foto consome o clique (não abre briefing nem marca rota por baixo)
    if (modo === 'visor') return // minimizado: o clique só expande (app.js)
    if (modo === 'explorar') marcadorClique.setLngLat(e.lngLat).addTo(map)
    onClick(e.lngLat.lat, e.lngLat.lng)
  })

  map.on('load', () => {
    map.addSource(ROUTE_ID, { type: 'geojson', data: vazio() })
    map.addLayer({
      id: ROUTE_ID,
      type: 'line',
      source: ROUTE_ID,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-width': 4, 'line-color': corPorStatus(SLOPE_COLOR_HEX.seguro) },
    })
    carregado = true
    onLoad()

  })
}

export function setCamadaVisivel(id, visivel) {
  map?.setLayoutProperty(id, 'visibility', visivel ? 'visible' : 'none')
}

export function setCamadaOpacidade(id, opacidade) {
  map?.setPaintProperty(id, 'raster-opacity', opacidade)
}

/** 'visor' (círculo) | 'explorar' | 'rota' -- cursor vira mira no modo rota. */
export function setModo(novo) {
  modo = novo
  if (!map) return
  map.getCanvas().style.cursor = modo === 'rota' ? 'crosshair' : ''
  if (modo !== 'explorar') marcadorClique.remove()
}

/** Depois de o contêiner mudar de tamanho (círculo <-> tela cheia). */
export function redimensionar() {
  map?.resize()
}

/** Centra no ponto ou, com rota, enquadra a rota inteira. */
export function centrar(p, rota = null) {
  if (!map) return
  const coords = (rota?.trechos_risco ?? []).flatMap((t) => [[t.de[1], t.de[0]], [t.para[1], t.para[0]]])
  if (coords.length) {
    const lons = coords.map((c) => c[0]), lats = coords.map((c) => c[1])
    map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 24, duration: 0, maxZoom: 18 })
  } else if (p) map.jumpTo({ center: [p.lon, p.lat], zoom: Math.max(map.getZoom(), 16) })
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
/** Parada do Curiosity onde foi tirado o panorama mostrado na barra (null tira). */
export function setPanorama(p) {
  posicionar(marcadorPano, p)
  if (p && marcadorPano) marcadorPano.getElement().title = `Panorama mais próximo · sol ${p.sol}`
}

let marcadoresEscala = []
/** Paradas intermediárias da rota. Quantidade varia,
 * então recria os marcadores a cada chamada em vez de reusar um fixo. */
export function setEscalas(escalas) {
  if (!map) return
  marcadoresEscala.forEach((m) => m.remove())
  marcadoresEscala = escalas.map((p) => marcador('h2g2-route-marker h2g2-route-marker--escala').setLngLat([p.lon, p.lat]).addTo(map))
}

export function setRota(rota) {
  if (!carregado) return
  map.getSource(ROUTE_ID).setData({
    type: 'FeatureCollection',
    features: (rota?.trechos_risco ?? []).map((t) => ({
      type: 'Feature',
      properties: { slope_status: t.status_previsto ?? t.slope_status }, // feature 06: inclui a previsão
      geometry: { type: 'LineString', coordinates: [[t.de[1], t.de[0]], [t.para[1], t.para[0]]] },
    })),
  })
}
