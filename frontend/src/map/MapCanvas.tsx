import { Map, Marker, NavigationControl } from 'maplibre-gl'
import type { MapMouseEvent } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef } from 'react'

import type { LayerMeta } from '../api/types'
import { buildStyle, TEST_BBOX_CENTER, TEST_BBOX_INITIAL_ZOOM } from './style'

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

    map.on('load', () => onMapReady(map))

    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  return <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />
}
