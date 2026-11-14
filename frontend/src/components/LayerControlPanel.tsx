import type { Map } from 'maplibre-gl'
import { useState } from 'react'

import { mosaicUrl } from '../api/client'
import { PLANNED_LAYERS, TOGGLEABLE_LAYERS } from '../map/layers'

const THUMB_SIZE = 32

interface LayerControlPanelProps {
  map: Map | null
  photosVisible: boolean
  onTogglePhotos: () => void
  photoCount: number
  roverTrackVisible: boolean
  onToggleRoverTrack: () => void
}

export function LayerControlPanel({
  map,
  photosVisible,
  onTogglePhotos,
  photoCount,
  roverTrackVisible,
  onToggleRoverTrack,
}: LayerControlPanelProps) {
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s-2)', minWidth: 0 }}>
            <img
              src={mosaicUrl(layer.id)}
              alt=""
              loading="lazy"
              style={{
                width: THUMB_SIZE,
                height: THUMB_SIZE,
                objectFit: 'cover',
                borderRadius: 'var(--r-1)',
                border: '1px solid var(--glass-rim)',
                flex: 'none',
                background: 'var(--n900)',
              }}
            />
            <span style={{ fontSize: 'var(--t-small)', color: 'var(--ink)' }}>{layer.label}</span>
          </div>
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
        // Parte de um grupo flex-column em App.tsx (junto com
        // ConditionsPanel) -- antes era `position: absolute` solto, e
        // como não tinha limite de altura/scroll próprio, o conteúdo
        // (que cresceu com as miniaturas de camada) ficava coberto pelo
        // painel de condições ancorado embaixo na mesma coluna (bug
        // real reportado pelo usuário, não um elemento "escondido" por
        // design). Flex + overflow próprio resolve isso de vez, sem
        // número mágico de altura que quebra de novo no futuro.
        flex: '1 1 auto',
        minHeight: 0,
        overflowY: 'auto',
        width: '100%',
        padding: 'var(--s-3) var(--s-4)',
      }}
    >
      <p className="h2g2-panel-title">Camadas</p>

      {baseLayers.map(renderLayerRow)}

      <div style={{ borderTop: '1px solid var(--glass-rim)', paddingTop: 'var(--s-2)', marginTop: 'var(--s-1)' }}>
        {overlayLayers.map(renderLayerRow)}

        <div className={`h2g2-layer-row ${photosVisible ? 'on' : ''}`}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--s-2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s-2)', minWidth: 0 }}>
              <div
                style={{
                  width: THUMB_SIZE,
                  height: THUMB_SIZE,
                  borderRadius: 'var(--r-1)',
                  border: '1px solid var(--glass-rim)',
                  background: 'var(--n900)',
                  display: 'grid',
                  placeItems: 'center',
                  flex: 'none',
                  color: '#f2b33d',
                  fontSize: 16,
                }}
              >
                📷
              </div>
              <span style={{ fontSize: 'var(--t-small)', color: 'var(--ink)' }}>Rastro do rover ({photoCount})</span>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={photosVisible}
              onClick={onTogglePhotos}
              className={`h2g2-switch ${photosVisible ? 'on' : ''}`}
            >
              <span />
            </button>
          </div>
        </div>

        <div className={`h2g2-layer-row ${roverTrackVisible ? 'on' : ''}`} style={{ marginTop: 'var(--s-2)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 'var(--s-2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s-2)', minWidth: 0 }}>
              <div
                style={{
                  width: THUMB_SIZE,
                  height: THUMB_SIZE,
                  borderRadius: 'var(--r-1)',
                  border: '1px solid var(--glass-rim)',
                  background: 'var(--n900)',
                  display: 'grid',
                  placeItems: 'center',
                  flex: 'none',
                  color: 'var(--hud-cyan)',
                  fontSize: 16,
                }}
              >
                〰️
              </div>
              <span
                style={{ fontSize: 'var(--t-small)', color: 'var(--ink)' }}
                title="Paradas reais do Curiosity, coloridas pela inclinação que o rover mediu no chão (não a do DTM) -- verde seguro, âmbar atenção, vermelho perigo (feature 08)."
              >
                Trilha do Curiosity (inclinação medida)
              </span>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={roverTrackVisible}
              onClick={onToggleRoverTrack}
              className={`h2g2-switch ${roverTrackVisible ? 'on' : ''}`}
            >
              <span />
            </button>
          </div>
        </div>
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
