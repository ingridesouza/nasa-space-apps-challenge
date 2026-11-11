import { useEffect, useState } from 'react'

import { getPoint } from '../api/client'
import type { PointResponse, RasterValue } from '../api/types'
import { SLOPE_VERDICT } from '../theme/verdict'
import { NearbyPhotosSection } from './NearbyPhotosSection'
import { ScienceTargetSection } from './ScienceTargetSection'

interface PointInfoPanelProps {
  point: { lat: number; lon: number } | null
  onClose: () => void
}

const CATEGORIA_LABEL: Record<string, string> = {
  topografica: 'Topografia',
  optica: 'Óptica',
  termica: 'Térmica',
  espectral_quimica: 'Mineralogia',
}

/** Preferência de qual camada de elevação vira o veredito principal --
 * a mais precisa disponível primeiro (DTM HiRISE 1m antes do MOLA
 * regional, bem mais grosseiro). */
const PRIORIDADE_ELEVACAO = ['dtm_hirise_1m', 'mola_topografia_regional']

function pickPrimaryElevation(rasterValues: Record<string, RasterValue>): [string, RasterValue] | null {
  for (const nome of PRIORIDADE_ELEVACAO) {
    if (rasterValues[nome]) return [nome, rasterValues[nome]]
  }
  const entries = Object.entries(rasterValues)
  return entries.length > 0 ? entries[0] : null
}

export function PointInfoPanel({ point, onClose }: PointInfoPanelProps) {
  const [data, setData] = useState<PointResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!point) return
    setLoading(true)
    setError(null)
    setData(null)

    getPoint(point.lat, point.lon)
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [point])

  if (!point) return null

  const rasterEntries = data ? Object.entries(data.raster_values) : []
  const primary = data ? pickPrimaryElevation(data.raster_values) : null
  const outrasFontes = primary ? rasterEntries.filter(([nome]) => nome !== primary[0]) : []

  return (
    <div
      key={`${point.lat},${point.lon}`}
      className="h2g2-panel"
      style={{
        position: 'absolute',
        top: 88,
        right: 'var(--s-4)',
        width: 300,
        maxHeight: 'calc(100vh - 104px)',
        overflowY: 'auto',
        padding: 'var(--s-4)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <p className="h2g2-panel-title">Briefing de segurança</p>
        <button onClick={onClose} className="h2g2-close-btn" aria-label="Fechar">
          ×
        </button>
      </div>

      <div className="h2g2-mono" style={{ fontSize: 'var(--t-small)', color: 'var(--hud-cyan)', marginBottom: 'var(--s-4)' }}>
        {point.lat.toFixed(5)}, {point.lon.toFixed(5)}
      </div>

      {loading && (
        <div className="h2g2-dim h2g2-mono" style={{ fontSize: 'var(--t-small)' }}>
          consultando /api/point...
        </div>
      )}
      {error && <div style={{ color: 'var(--danger)', fontSize: 'var(--t-small)' }}>{error}</div>}

      {data && (
        <>
          {primary === null ? (
            <div className="h2g2-empty-state">
              Fora da área de teste com dado baixado (ver PROXIMOS-PASSOS.md).
            </div>
          ) : (
            (() => {
              const [layerName, v] = primary
              const veredito = v.slope_status ? SLOPE_VERDICT[v.slope_status] : null
              return (
                <div
                  style={{
                    border: `1px solid ${veredito ? veredito.color : 'var(--glass-rim)'}`,
                    borderRadius: 'var(--r-2)',
                    padding: 'var(--s-3)',
                    marginBottom: 'var(--s-4)',
                    background: veredito ? `color-mix(in srgb, ${veredito.color} 10%, transparent)` : 'transparent',
                  }}
                >
                  {veredito && (
                    <div
                      className="h2g2-mono"
                      style={{
                        color: veredito.color,
                        fontSize: 'var(--t-small)',
                        fontWeight: 600,
                        marginBottom: 'var(--s-2)',
                      }}
                    >
                      ● {veredito.label}
                    </div>
                  )}
                  <div className="h2g2-mono" style={{ fontSize: 'var(--t-3)', color: 'var(--ink)', lineHeight: 1.1 }}>
                    {v.valor.toFixed(1)}
                    <span style={{ fontSize: 'var(--t-small)', color: 'var(--ink-3)' }}>m</span>
                  </div>
                  {v.slope_deg !== undefined && (
                    <div className="h2g2-dim h2g2-mono" style={{ fontSize: 'var(--t-small)' }}>
                      slope {v.slope_deg.toFixed(2)}°
                    </div>
                  )}
                  <div className="h2g2-dim" style={{ fontSize: 'var(--t-micro)', marginTop: 'var(--s-1)' }}>
                    {CATEGORIA_LABEL[v.categoria] ?? v.categoria} · {layerName}
                  </div>
                </div>
              )
            })()
          )}

          {outrasFontes.length > 0 && (
            <div style={{ marginBottom: 'var(--s-4)' }}>
              <p className="h2g2-panel-title" style={{ fontSize: 'var(--t-micro)' }}>
                Outras fontes de elevação
              </p>
              {outrasFontes.map(([layerName, v]) => (
                <div key={layerName} className="h2g2-dim h2g2-mono" style={{ fontSize: 'var(--t-small)' }}>
                  {layerName}: {v.valor.toFixed(1)}m
                  {v.slope_deg !== undefined && ` · ${v.slope_deg.toFixed(2)}°`}
                </div>
              ))}
            </div>
          )}

          <NearbyPhotosSection photos={data.nearby_photos} />
          <ScienceTargetSection target={data.science_target} />
        </>
      )}
    </div>
  )
}
