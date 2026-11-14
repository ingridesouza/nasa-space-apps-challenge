import type { GeoJSONSource, MapMouseEvent } from 'maplibre-gl'
import { Map, Marker, NavigationControl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef } from 'react'

import { getRoverTrack } from '../api/client'
import type { LayerMeta, RouteOption, RoverPhotoPin, RoverStop } from '../api/types'
import { SLOPE_COLOR_HEX } from '../theme/verdict'
import { baseLayersBounds, buildStyle, dataBounds, minZoomToCover, TEST_BBOX_CENTER, TEST_BBOX_INITIAL_ZOOM } from './style'

export type PickMode = 'point' | 'pick-origin' | 'pick-destination'

export const ROVER_TRACK_LINE_ID = 'rover_track_line'
export const ROVER_TRACK_STOPS_ID = 'rover_track_stops'

/** Trilha do Curiosity (feature 08, memória do terreno): uma linha
 * ligando as paradas em ordem de sol + um círculo por parada colorido
 * pela inclinação que o rover mediu no chão (mesmos limites 15°/20° do
 * DTM). Mostra onde o mapa de relevo erra.
 *
 * Começa invisível (`visibility: 'none'`) -- antes aparecia sempre
 * ligada, sem nome nem toggle em lugar nenhum da UI, parecendo um bug
 * ("que linha é essa?", reportado pelo usuário). Agora segue o mesmo
 * padrão de toda outra camada: entra desligada por padrão (como
 * Relevo/THEMIS) e liga pelo LayerControlPanel. */
function addRoverTrack(map: Map, stops: RoverStop[], visivel: boolean) {
  map.addSource('rover_track', {
    type: 'geojson',
    data: {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {},
          geometry: { type: 'LineString', coordinates: stops.map((s) => [s.lon, s.lat]) },
        },
        ...stops.map((s) => ({
          type: 'Feature' as const,
          properties: { status: s.status, tilt: s.tilt, sol: s.sol },
          geometry: { type: 'Point' as const, coordinates: [s.lon, s.lat] },
        })),
      ],
    },
  })
  const visibility = visivel ? 'visible' : 'none'
  map.addLayer({
    id: ROVER_TRACK_LINE_ID,
    type: 'line',
    source: 'rover_track',
    filter: ['==', ['geometry-type'], 'LineString'],
    layout: { visibility },
    paint: { 'line-color': '#ffffff', 'line-opacity': 0.35, 'line-width': 1 },
  })
  map.addLayer({
    id: ROVER_TRACK_STOPS_ID,
    type: 'circle',
    source: 'rover_track',
    filter: ['==', ['geometry-type'], 'Point'],
    layout: { visibility },
    paint: {
      'circle-radius': ['match', ['get', 'status'], 'seguro', 3, 6],
      'circle-color': [
        'match',
        ['get', 'status'],
        'perigo',
        SLOPE_COLOR_HEX.perigo,
        'atencao',
        SLOPE_COLOR_HEX.atencao,
        SLOPE_COLOR_HEX.seguro,
      ],
      'circle-stroke-color': '#05070a',
      'circle-stroke-width': 1,
    },
  })
}

interface MapCanvasProps {
  layersMeta: LayerMeta[]
  pickMode: PickMode
  onMapClick: (lat: number, lon: number) => void
  onMapReady: (map: Map) => void
  routeOrigin: [number, number] | null
  routeDestination: [number, number] | null
  activeRoute: RouteOption | null
  photos: RoverPhotoPin[]
  photosVisible: boolean
  onPhotoClick: (photo: RoverPhotoPin) => void
  onZoomChange: (zoom: number) => void
  roverTrackVisible: boolean
}

const ROUTE_SOURCE_ID = 'h2g2-route-line'
const ROUTE_LAYER_ID = 'h2g2-route-line'
const PHOTOS_SOURCE_ID = 'h2g2-rover-photos'
const PHOTOS_LAYER_ID = 'h2g2-rover-photos'

function routeMarkerEl(kind: 'origin' | 'destination'): HTMLDivElement {
  const el = document.createElement('div')
  el.className = `h2g2-route-marker h2g2-route-marker--${kind}`
  return el
}

/** Wrapper fino do MapLibre em React -- usa a API imperativa direto
 * (via ref) em vez de uma lib como react-map-gl, porque precisamos de
 * controle fino sobre paint/layout properties por camada a partir do
 * LayerControlPanel (toggle/opacidade), e isso fica mais direto assim. */
export function MapCanvas({
  layersMeta,
  pickMode,
  onMapClick,
  onMapReady,
  routeOrigin,
  routeDestination,
  activeRoute,
  photos,
  photosVisible,
  onPhotoClick,
  onZoomChange,
  roverTrackVisible,
}: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<Map | null>(null)
  const loadedRef = useRef(false)
  const markerRef = useRef<Marker | null>(null)
  const originMarkerRef = useRef<Marker | null>(null)
  const destMarkerRef = useRef<Marker | null>(null)
  const pickModeRef = useRef<PickMode>(pickMode)
  const onMapClickRef = useRef(onMapClick)
  const onPhotoClickRef = useRef(onPhotoClick)
  const onZoomChangeRef = useRef(onZoomChange)
  const roverTrackVisibleRef = useRef(roverTrackVisible)

  useEffect(() => {
    roverTrackVisibleRef.current = roverTrackVisible
  }, [roverTrackVisible])

  useEffect(() => {
    onMapClickRef.current = onMapClick
  }, [onMapClick])

  useEffect(() => {
    onPhotoClickRef.current = onPhotoClick
  }, [onPhotoClick])

  useEffect(() => {
    onZoomChangeRef.current = onZoomChange
  }, [onZoomChange])

  useEffect(() => {
    pickModeRef.current = pickMode
    // cursor vira mira durante o modo rota -- feedback imediato de que
    // o clique no mapa agora marca origem/destino, não abre o briefing
    // de ponto (eram indistinguíveis antes, confundia o usuário).
    const canvas = mapRef.current?.getCanvas()
    if (canvas) canvas.style.cursor = pickMode === 'point' ? '' : 'crosshair'

    // o crosshair de "último ponto clicado" nunca era removido ao
    // entrar no modo rota -- ficava preso na tela num lugar antigo,
    // sem relação com origem/destino atuais (bug real reportado: "o
    // traço não cai onde eu cliquei", na verdade era esse marcador
    // velho confundindo a leitura, não a rota em si).
    if (pickMode !== 'point') {
      markerRef.current?.remove()
    }
  }, [pickMode])

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const bounds = dataBounds(layersMeta)
    const baseBounds = baseLayersBounds(layersMeta)
    const rect = containerRef.current.getBoundingClientRect()
    // sem isso, dar zoom out revela a área real "flutuando" numa tela
    // toda preta -- maxBounds só trava o PAN, não o zoom out (bug
    // reportado pelo usuário: "parece mapa quebrado"). Usa o bbox só
    // das camadas base (CTX/HiRISE), não a união com todas -- ver
    // baseLayersBounds.
    const minZoom = baseBounds ? minZoomToCover(baseBounds, rect.width, rect.height) : undefined

    const map = new Map({
      container: containerRef.current,
      style: buildStyle(layersMeta),
      center: TEST_BBOX_CENTER,
      zoom: TEST_BBOX_INITIAL_ZOOM,
      maxBounds: bounds ?? undefined,
      minZoom,
      attributionControl: false,
    })

    map.addControl(new NavigationControl({ showCompass: false }), 'bottom-right')

    const el = document.createElement('div')
    el.className = 'h2g2-crosshair'
    const dot = document.createElement('div')
    dot.className = 'h2g2-crosshair-dot'
    el.appendChild(dot)
    markerRef.current = new Marker({ element: el })

    map.on('click', (e: MapMouseEvent) => {
      if (pickModeRef.current === 'point') {
        markerRef.current?.setLngLat(e.lngLat).addTo(map)
      }
      onMapClickRef.current(e.lngLat.lat, e.lngLat.lng)
    })

    // feedback de zoom atual -- usuário pediu pra saber até onde faz
    // sentido dar zoom in antes de começar a borrar (ver LAYER_MAXZOOM
    // em style.ts, exibido no TopHud).
    //
    // `zoom` dispara dezenas de vezes por segundo durante o gesto --
    // chamar setState do React (lá em App.tsx) em TODO tick trava o
    // zoom de verdade, porque força o app inteiro a re-renderizar no
    // meio da animação (bug real reportado pelo usuário: "trava
    // bastante"). Throttle pra ~8/s mantém o número parecendo ao vivo
    // sem sufocar o React; `zoomend` garante que o valor final fique
    // sempre exato, mesmo que o throttle tenha pulado o último tick.
    let ultimoEnvioZoom = 0
    map.on('zoom', () => {
      const agora = performance.now()
      if (agora - ultimoEnvioZoom > 120) {
        ultimoEnvioZoom = agora
        onZoomChangeRef.current(map.getZoom())
      }
    })
    map.on('zoomend', () => onZoomChangeRef.current(map.getZoom()))

    map.on('load', () => {
      map.addSource(ROUTE_SOURCE_ID, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addLayer({
        id: ROUTE_LAYER_ID,
        type: 'line',
        source: ROUTE_SOURCE_ID,
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-width': 4,
          'line-color': [
            'match',
            ['get', 'slope_status'],
            'seguro',
            SLOPE_COLOR_HEX.seguro,
            'atencao',
            SLOPE_COLOR_HEX.atencao,
            'perigo',
            SLOPE_COLOR_HEX.perigo,
            SLOPE_COLOR_HEX.seguro,
          ],
        },
      })

      map.addSource(PHOTOS_SOURCE_ID, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addLayer({
        id: PHOTOS_LAYER_ID,
        type: 'circle',
        source: PHOTOS_SOURCE_ID,
        paint: {
          'circle-radius': 5,
          // hex literal (mesma cor de --amber em tokens.css) -- paint
          // property do MapLibre não resolve var() de CSS, ver
          // SLOPE_COLOR_HEX acima pro mesmo motivo.
          'circle-color': '#f2b33d',
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#0a0a0b',
        },
      })

      // pin de foto consome o clique (preventDefault) pra não também
      // disparar o clique genérico do mapa (abriria o briefing de ponto
      // ou marcaria origem/destino da rota por cima)
      map.on('click', PHOTOS_LAYER_ID, (e) => {
        e.preventDefault()
        const feature = e.features?.[0]
        if (!feature) return
        const props = feature.properties as { lat: number; lon: number; sol: number; camera: string; url: string }
        onPhotoClickRef.current(props)
      })
      map.on('mouseenter', PHOTOS_LAYER_ID, () => {
        map.getCanvas().style.cursor = 'pointer'
      })
      map.on('mouseleave', PHOTOS_LAYER_ID, () => {
        map.getCanvas().style.cursor = pickModeRef.current === 'point' ? '' : 'crosshair'
      })

      loadedRef.current = true
      onZoomChangeRef.current(map.getZoom())
      onMapReady(map)

      // trilha do Curiosity (feature 08) -- falha silenciosa: sem ela o
      // mapa continua útil (mesmo padrão da nomenclatura em App.tsx).
      getRoverTrack()
        .then((stops) => addRoverTrack(map, stops, roverTrackVisibleRef.current))
        .catch(() => {})
    })

    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
      loadedRef.current = false
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (routeOrigin) {
      if (!originMarkerRef.current) originMarkerRef.current = new Marker({ element: routeMarkerEl('origin') })
      originMarkerRef.current.setLngLat([routeOrigin[1], routeOrigin[0]]).addTo(map)
    } else {
      originMarkerRef.current?.remove()
    }
  }, [routeOrigin])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (routeDestination) {
      if (!destMarkerRef.current) destMarkerRef.current = new Marker({ element: routeMarkerEl('destination') })
      destMarkerRef.current.setLngLat([routeDestination[1], routeDestination[0]]).addTo(map)
    } else {
      destMarkerRef.current?.remove()
    }
  }, [routeDestination])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    const source = map.getSource(ROUTE_SOURCE_ID) as GeoJSONSource | undefined
    if (!source) return

    if (!activeRoute) {
      source.setData({ type: 'FeatureCollection', features: [] })
      return
    }

    source.setData({
      type: 'FeatureCollection',
      features: activeRoute.trechos_risco.map((trecho) => ({
        type: 'Feature',
        properties: { slope_status: trecho.slope_status },
        geometry: {
          type: 'LineString',
          coordinates: [
            [trecho.de[1], trecho.de[0]],
            [trecho.para[1], trecho.para[0]],
          ],
        },
      })),
    })
  }, [activeRoute])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    const source = map.getSource(PHOTOS_SOURCE_ID) as GeoJSONSource | undefined
    if (!source) return

    source.setData({
      type: 'FeatureCollection',
      features: photos.map((p) => ({
        type: 'Feature',
        properties: { lat: p.lat, lon: p.lon, sol: p.sol, camera: p.camera, url: p.url },
        geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
      })),
    })
  }, [photos])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current) return
    map.setLayoutProperty(PHOTOS_LAYER_ID, 'visibility', photosVisible ? 'visible' : 'none')
  }, [photosVisible])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadedRef.current || !map.getLayer(ROVER_TRACK_LINE_ID)) return
    const visibility = roverTrackVisible ? 'visible' : 'none'
    map.setLayoutProperty(ROVER_TRACK_LINE_ID, 'visibility', visibility)
    map.setLayoutProperty(ROVER_TRACK_STOPS_ID, 'visibility', visibility)
  }, [roverTrackVisible])

  return <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />
}
