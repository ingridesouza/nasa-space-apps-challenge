import { useEffect, useState } from 'react'

import { getPoint } from '../api/client'
import type { Alerta, NomenclatureFeature, PointResponse } from '../api/types'
import { nearestNomenclature } from '../map/nomenclature'
import { NearbyPhotosSection } from './NearbyPhotosSection'
import { ScienceTargetSection } from './ScienceTargetSection'
import { VerdictBadge } from './VerdictBadge'

interface PointInfoPanelProps {
  point: { lat: number; lon: number } | null
  onClose: () => void
  nomenclature: NomenclatureFeature[]
}

/** Alertas da feature 08 (`api/alertas.py`): perigo/atenção usam as
 * mesmas cores do veredito de inclinação. */
const ALERTA_COR: Record<Alerta['nivel'], string> = {
  perigo: 'var(--verdict-perigo)',
  atencao: 'var(--verdict-atencao)',
  info: 'var(--ink-3)',
}

const CATEGORIA_LABEL: Record<string, string> = {
  topografica: 'Topografia',
  optica: 'Óptica',
  termica: 'Térmica',
  espectral_quimica: 'Mineralogia',
}

/** Nome da camada que virou o valor "oficial" de `elevacao_m`/`slope_deg`
 * no topo da resposta (ver `PRIORIDADE_ELEVACAO` em
 * `api/raster_sampling.py`) -- usado só pra exibir a legenda da fonte. */
function primaryLayerName(fontes: Record<string, unknown>): string | null {
  if ('dtm_hirise_1m' in fontes) return 'dtm_hirise_1m'
  if ('mola_topografia_regional' in fontes) return 'mola_topografia_regional'
  const nomes = Object.keys(fontes)
  return nomes.length > 0 ? nomes[0] : null
}

export function PointInfoPanel({ point, onClose, nomenclature }: PointInfoPanelProps) {
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

  const layerName = data ? primaryLayerName(data.raster_values.fontes) : null
  const hasPrimary = data !== null && data.raster_values.elevacao_m !== null
  const outrasFontes = data
    ? Object.entries(data.raster_values.fontes).filter(([nome]) => nome !== layerName)
    : []
  const perto = nearestNomenclature(nomenclature, point.lat, point.lon)

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

      <div className="h2g2-mono" style={{ fontSize: 'var(--t-small)', color: 'var(--hud-cyan)' }}>
        {point.lat.toFixed(5)}, {point.lon.toFixed(5)}
      </div>

      {perto && (
        <div className="h2g2-dim" style={{ fontSize: 'var(--t-micro)', marginBottom: 'var(--s-4)' }}>
          perto de{' '}
          <a
            href={perto.feature.fonte_url}
            target="_blank"
            rel="noreferrer"
            style={{ color: 'var(--ink-2)' }}
            title={`Nome oficial IAU/USGS · ${perto.feature.tipo}`}
          >
            {perto.feature.nome}
          </a>{' '}
          ({(perto.distance_m / 1000).toFixed(1)}km)
        </div>
      )}
      {!perto && <div style={{ marginBottom: 'var(--s-4)' }} />}

      {loading && (
        <div className="h2g2-dim h2g2-mono" style={{ fontSize: 'var(--t-small)' }}>
          consultando /api/point...
        </div>
      )}
      {error && <div style={{ color: 'var(--danger)', fontSize: 'var(--t-small)' }}>{error}</div>}

      {data && data.alertas.length > 0 && (
        <div style={{ marginBottom: 'var(--s-4)' }}>
          {data.alertas.map((a) => (
            <div
              key={a.tipo + a.mensagem}
              className="h2g2-mono"
              title={`fonte: ${a.fonte}`}
              style={{ color: ALERTA_COR[a.nivel], fontSize: 'var(--t-small)', marginBottom: 'var(--s-1)' }}
            >
              ● {a.mensagem}
            </div>
          ))}
        </div>
      )}

      {data && (
        <>
          {!hasPrimary || !data ? (
            <div className="h2g2-empty-state">
              Fora da área de teste com dado baixado (ver PROXIMOS-PASSOS.md).
            </div>
          ) : (
            (() => {
              const rv = data.raster_values
              const categoria = layerName ? rv.fontes[layerName]?.categoria : undefined
              return (
                <div style={{ marginBottom: 'var(--s-4)' }}>
                  {rv.slope_status && <VerdictBadge status={rv.slope_status} />}
                  <div className="h2g2-card" style={{ marginTop: 'var(--s-2)' }}>
                    <div className="h2g2-display" style={{ fontSize: 'var(--t-3)', color: 'var(--ink)', lineHeight: 1.1 }}>
                      {rv.elevacao_m!.toFixed(1)}
                      <span className="h2g2-mono" style={{ fontSize: 'var(--t-small)', color: 'var(--ink-3)' }}>
                        {' '}m
                      </span>
                    </div>
                    {rv.slope_deg !== null && (
                      <div className="h2g2-dim h2g2-mono" style={{ fontSize: 'var(--t-small)' }}>
                        slope {rv.slope_deg!.toFixed(2)}°
                      </div>
                    )}
                    <div className="h2g2-dim" style={{ fontSize: 'var(--t-micro)', marginTop: 'var(--s-1)' }}>
                      {categoria ? (CATEGORIA_LABEL[categoria] ?? categoria) : ''} · {layerName}
                    </div>
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
              {outrasFontes.map(([nome, v]) => (
                <div key={nome} className="h2g2-dim h2g2-mono" style={{ fontSize: 'var(--t-small)' }}>
                  {nome}: {v.valor.toFixed(1)}m
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
