import type { Map } from 'maplibre-gl'
import { useState } from 'react'

import { PLANNED_LAYERS, TOGGLEABLE_LAYERS } from '../map/layers'

interface LayerControlPanelProps {
  map: Map | null
}

export function LayerControlPanel({ map }: LayerControlPanelProps) {
  const [layerState, setLayerState] = useState(() =>
    Object.fromEntries(TOGGLEABLE_LAYERS.map((l) => [l.id, { visible: l.defaultVisible, opacity: l.defaultOpacity }])),
  )

  function toggle(id: string) {
    if (!map) return
    const next = !layerState[id].visible
    map.setLayoutProperty(id, 'visibility', next ? 'visible' : 'none')
    setLayerState((s) => ({ ...s, [id]: { ...s[id], visible: next } }))
  }

  function setOpacity(id: string, opacity: number) {
    if (!map) return
    map.setPaintProperty(id, 'raster-opacity', opacity)
    setLayerState((s) => ({ ...s, [id]: { ...s[id], opacity } }))
  }

  function renderLayerRow(layer: (typeof TOGGLEABLE_LAYERS)[number]) {
    const state = layerState[layer.id]
    return (
      <div key={layer.id} className={`h2g2-layer-row ${state.visible ? 'on' : ''}`} style={{ marginBottom: 'var(--s-2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--s-2)' }}>
          <span style={{ fontSize: 'var(--t-small)', color: 'var(--ink)' }}>{layer.label}</span>
          <button
            type="button"
            role="switch"
            aria-checked={state.visible}
            onClick={() => toggle(layer.id)}
            className={`h2g2-switch ${state.visible ? 'on' : ''}`}
          >
            <span />
          </button>
        </div>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={state.opacity}
          disabled={!state.visible}
          onChange={(e) => setOpacity(layer.id, Number(e.target.value))}
          style={{ width: '100%' }}
        />
      </div>
    )
  }

  const baseLayers = TOGGLEABLE_LAYERS.filter((l) => l.grupo === 'base')
  const overlayLayers = TOGGLEABLE_LAYERS.filter((l) => l.grupo === 'overlay')

  return (
    <div
      className="h2g2-panel"
      style={{
        position: 'absolute',
        top: 88,
        left: 'var(--s-4)',
        width: 240,
        padding: 'var(--s-3) var(--s-4)',
      }}
    >
      <p className="h2g2-panel-title">Camadas</p>

      {baseLayers.map(renderLayerRow)}

      <div style={{ borderTop: '1px solid var(--glass-rim)', paddingTop: 'var(--s-2)', marginTop: 'var(--s-1)' }}>
        {overlayLayers.map(renderLayerRow)}
      </div>

      <div style={{ borderTop: '1px solid var(--glass-rim)', paddingTop: 'var(--s-3)', marginTop: 'var(--s-1)' }}>
        {PLANNED_LAYERS.map((layer) => (
          <div
            key={layer.id}
            className="h2g2-dim"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: 'var(--t-small)',
              marginBottom: 'var(--s-2)',
            }}
            title={layer.motivo}
          >
            <span>{layer.label}</span>
            <span className="h2g2-mono" style={{ fontSize: 'var(--t-micro)' }}>
              {layer.status === 'fora_de_escopo' ? 'fora de escopo' : 'em breve'}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
