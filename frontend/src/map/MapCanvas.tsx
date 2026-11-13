import { Map, Marker, NavigationControl } from 'maplibre-gl'
import type { MapMouseEvent } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef } from 'react'

import { getRoverTrack } from '../api/client'
import type { LayerMeta, RoverStop } from '../api/types'
import { SLOPE_HEX } from '../theme/verdict'
import { buildStyle, TEST_BBOX_CENTER, TEST_BBOX_INITIAL_ZOOM } from './style'

/** Trilha do Curiosity (feature 08, memória do terreno): uma linha
 * ligando as paradas em ordem de sol + um círculo por parada colorido
 * pela inclinação que o rover mediu no chão (mesmos limites 15°/20° do
 * DTM). Mostra onde o mapa de relevo erra. */
function addRoverTrack(map: Map, stops: RoverStop[]) {
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
  map.addLayer({
    id: 'rover_track_line',
    type: 'line',
    source: 'rover_track',
    filter: ['==', ['geometry-type'], 'LineString'],
    paint: { 'line-color': '#ffffff', 'line-opacity': 0.35, 'line-width': 1 },
  })
  map.addLayer({
    id: 'rover_track_stops',
    type: 'circle',
    source: 'rover_track',
    filter: ['==', ['geometry-type'], 'Point'],
    paint: {
      'circle-radius': ['match', ['get', 'status'], 'seguro', 3, 6],
      'circle-color': ['match', ['get', 'status'], 'perigo', SLOPE_HEX.perigo, 'atencao', SLOPE_HEX.atencao, SLOPE_HEX.seguro],
      'circle-stroke-color': '#05070a',
      'circle-stroke-width': 1,
    },
  })
}

interface MapCanvasProps {
  layersMeta: LayerMeta[]
  onPointClick: (lat: number, lon: number) => void
  onMapReady: (map: Map) => void
}

/** Wrapper fino do MapLibre em React -- usa a API imperativa direto
 * (via ref) em vez de uma lib como react-map-gl, porque precisamos de
 * controle fino sobre paint/layout properties por camada a partir do
 * LayerControlPanel (toggle/opacidade), e isso fica mais direto assim. */
export function MapCanvas({ layersMeta, onPointClick, onMapReady }: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<Map | null>(null)
  const markerRef = useRef<Marker | null>(null)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const map = new Map({
      container: containerRef.current,
      style: buildStyle(layersMeta),
      center: TEST_BBOX_CENTER,
      zoom: TEST_BBOX_INITIAL_ZOOM,
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
      markerRef.current?.setLngLat(e.lngLat).addTo(map)
      onPointClick(e.lngLat.lat, e.lngLat.lng)
    })

    map.on('load', () => {
      onMapReady(map)
      // Falha silenciosa: sem trilha o mapa continua útil (mesmo padrão
      // da nomenclatura em App.tsx).
      getRoverTrack()
        .then((stops) => addRoverTrack(map, stops))
        .catch(() => {})
    })

    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  return <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />
}
