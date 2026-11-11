import type { Map } from 'maplibre-gl'
import { useEffect, useState } from 'react'

import { getConditions, getLayers } from './api/client'
import type { ConditionsResponse, LayerMeta } from './api/types'
import { ConditionsPanel } from './components/ConditionsPanel'
import { LayerControlPanel } from './components/LayerControlPanel'
import { PointInfoPanel } from './components/PointInfoPanel'
import { TopHud } from './components/TopHud'
import { MapCanvas } from './map/MapCanvas'

export default function App() {
  const [map, setMap] = useState<Map | null>(null)
  const [selectedPoint, setSelectedPoint] = useState<{ lat: number; lon: number } | null>(null)
  const [layersMeta, setLayersMeta] = useState<LayerMeta[] | null>(null)
  const [layersError, setLayersError] = useState<string | null>(null)
  const [conditions, setConditions] = useState<ConditionsResponse | null>(null)
  const [conditionsError, setConditionsError] = useState<string | null>(null)

  useEffect(() => {
    getLayers()
      .then(setLayersMeta)
      .catch((e) => setLayersError(String(e)))

    getConditions()
      .then(setConditions)
      .catch((e) => setConditionsError(String(e)))
  }, [])

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden' }}>
      {layersMeta && (
        <MapCanvas
          layersMeta={layersMeta}
          onMapReady={setMap}
          onPointClick={(lat, lon) => setSelectedPoint({ lat, lon })}
        />
      )}

      {!layersMeta && !layersError && (
        <div className="h2g2-mono h2g2-dim" style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>
          carregando camadas da API...
        </div>
      )}

      {layersError && (
        <div
          className="h2g2-mono"
          style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: 'var(--h2g2-danger)' }}
        >
          Não consegui falar com a API ({layersError}). Ela está rodando?
        </div>
      )}

      <div className="h2g2-vignette" />
      <div className="h2g2-corner h2g2-corner--tl" />
      <div className="h2g2-corner h2g2-corner--tr" />
      <div className="h2g2-corner h2g2-corner--bl" />
      <div className="h2g2-corner h2g2-corner--br" />
      <TopHud lastClick={selectedPoint} sol={conditions?.sol ?? null} />
      <LayerControlPanel map={map} />
      <ConditionsPanel conditions={conditions} error={conditionsError} />
      <PointInfoPanel point={selectedPoint} onClose={() => setSelectedPoint(null)} />
    </div>
  )
}
