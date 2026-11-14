import { useEffect, useState } from 'react'

import { getRoute } from '../api/client'
import type { RouteOption, RouteResponse, SlopeStatus } from '../api/types'
import { SLOPE_VERDICT } from '../theme/verdict'
import { VerdictBadge } from './VerdictBadge'

interface RoutePanelProps {
  origin: { lat: number; lon: number } | null
  destination: { lat: number; lon: number } | null
  onClose: () => void
  onReset: () => void
  onActiveRouteChange: (route: RouteOption | null) => void
}

const TIPO_LABEL: Record<RouteOption['tipo'], string> = {
  mais_segura: 'Mais segura',
  mais_rapida: 'Mais rápida',
}

/** Capacidade de O2 de referência pra virar a barra de progresso --
 * ilustrativa/simulada, mesma linguagem do resto do modelo de O2/tempo
 * em api/route_planning.py (não é especificação real de um traje). */
const CAPACIDADE_O2_L_SIMULADA = 400
const RESERVA_MINIMA_PCT = 0.2

function worstSlopeStatus(rota: RouteOption): SlopeStatus {
  if (rota.trechos_risco.some((t) => t.slope_status === 'perigo')) return 'perigo'
  if (rota.trechos_risco.some((t) => t.slope_status === 'atencao')) return 'atencao'
  return 'seguro'
}

/** Mini gráfico de perfil de elevação -- SVG inline, sem lib nova. */
function ElevationProfile({ perfil }: { perfil: RouteOption['perfil_elevacao'] }) {
  if (perfil.length < 2) return null

  const w = 260
  const h = 56
  const elevacoes = perfil.map((p) => p.elevacao_m)
  const distMax = perfil[perfil.length - 1].distancia_acumulada_m || 1
  const elevMin = Math.min(...elevacoes)
  const elevMax = Math.max(...elevacoes)
  const elevRange = elevMax - elevMin || 1

  const pontos = perfil
    .map((p) => {
      const x = (p.distancia_acumulada_m / distMax) * w
      const y = h - ((p.elevacao_m - elevMin) / elevRange) * h
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <polyline points={pontos} fill="none" stroke="var(--hud-cyan)" strokeWidth={1.5} />
    </svg>
  )
}

/** Feature 02: painel de planejamento de rota. Clique na origem, clique
 * no destino, escolhe entre "mais segura"/"mais rápida" -- mesmo A* real
 * sobre o DTM, pesos diferentes (ver api/route_planning.py). */
export function RoutePanel({ origin, destination, onClose, onReset, onActiveRouteChange }: RoutePanelProps) {
  const [data, setData] = useState<RouteResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tipo, setTipo] = useState<RouteOption['tipo']>('mais_segura')
  // O aviso de areia é genérico da região do boxwork, não calculado por
  // rota -- repeti-lo em toda rota recalculada parecia bug (reportado
  // pelo usuário). Mostra cheio na primeira vez da sessão; depois fica
  // reduzido a um link, sem sumir de vez (ainda é informação real).
  const [avisoExpandido, setAvisoExpandido] = useState(true)

  useEffect(() => {
    setData(null)
    setError(null)
    if (!origin || !destination) return

    setLoading(true)
    getRoute(origin.lat, origin.lon, destination.lat, destination.lon)
      .then((resp) => {
        setData(resp)
        setTipo('mais_segura')
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [origin, destination])

  useEffect(() => {
    const rota = data?.rotas.find((r) => r.tipo === tipo) ?? null
    onActiveRouteChange(rota)
    return () => onActiveRouteChange(null)
  }, [data, tipo])

  const rotaAtiva = data?.rotas.find((r) => r.tipo === tipo) ?? null

  return (
    <div
      className="h2g2-panel"
      style={{
        position: 'absolute',
        top: 88,
        right: 'var(--s-4)',
        width: 300,
        maxHeight: 'calc(100vh - 104px)',
        overflowY: 'auto',
        overflowX: 'hidden',
        padding: 'var(--s-4)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <p className="h2g2-panel-title">Planejar rota</p>
        <button onClick={onClose} className="h2g2-close-btn" aria-label="Fechar">
          ×
        </button>
      </div>

      {!origin && <div className="h2g2-dim h2g2-mono" style={{ fontSize: 'var(--t-small)' }}>Clique no mapa pra marcar a origem.</div>}
      {origin && !destination && (
        <div className="h2g2-dim h2g2-mono" style={{ fontSize: 'var(--t-small)' }}>
          Origem: {origin.lat.toFixed(5)}, {origin.lon.toFixed(5)}
          <br />
          Clique no mapa pra marcar o destino.
        </div>
      )}

      {origin && destination && (
        <>
          <button
            onClick={onReset}
            className="h2g2-mono h2g2-dim"
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              marginBottom: 'var(--s-3)',
              fontSize: 'var(--t-micro)',
              textDecoration: 'underline',
              cursor: 'pointer',
            }}
          >
            ↺ escolher outros pontos
          </button>

          {loading && (
            <div className="h2g2-dim h2g2-mono" style={{ fontSize: 'var(--t-small)' }}>
              calculando rota (A* sobre o DTM)...
            </div>
          )}
          {error && <div style={{ color: 'var(--danger)', fontSize: 'var(--t-small)' }}>{error}</div>}

          {data && (
            <>
              <div style={{ display: 'flex', gap: 'var(--s-2)', marginBottom: 'var(--s-3)' }}>
                {data.rotas.map((r) => (
                  <button
                    key={r.tipo}
                    onClick={() => setTipo(r.tipo)}
                    className="h2g2-mono"
                    style={{
                      flex: 1,
                      padding: 'var(--s-2)',
                      fontSize: 'var(--t-micro)',
                      border: `1px solid ${r.tipo === tipo ? 'var(--hud-cyan)' : 'var(--glass-rim)'}`,
                      borderRadius: 'var(--r-2)',
                      background: r.tipo === tipo ? 'rgba(143, 180, 232, 0.12)' : 'transparent',
                      color: r.tipo === tipo ? 'var(--hud-cyan)' : 'var(--ink-3)',
                      cursor: 'pointer',
                    }}
                  >
                    {TIPO_LABEL[r.tipo]}
                  </button>
                ))}
              </div>

              {rotaAtiva &&
                (() => {
                  const status = worstSlopeStatus(rotaAtiva)
                  const o2Pct = (rotaAtiva.o2_estimado_l / CAPACIDADE_O2_L_SIMULADA) * 100
                  const o2DentroDaReserva = o2Pct <= (1 - RESERVA_MINIMA_PCT) * 100
                  return (
                    <div style={{ marginBottom: 'var(--s-3)' }}>
                      <VerdictBadge
                        status={status}
                        checklist={[
                          { ok: status !== 'perigo', label: 'Nenhum trecho acima do limite de 20°' },
                          { ok: o2DentroDaReserva, label: 'O₂ dentro da reserva simulada (20%)' },
                        ]}
                      />

                      <div className="h2g2-card h2g2-stat-grid" style={{ marginTop: 'var(--s-2)' }}>
                        <div>
                          <span className="h2g2-stat-label">Distância</span>
                          <span className="h2g2-stat-value">{rotaAtiva.distancia_m.toFixed(0)}m</span>
                        </div>
                        <div>
                          <span className="h2g2-stat-label">Tempo</span>
                          <span className="h2g2-stat-value">~{rotaAtiva.tempo_estimado_min.toFixed(0)} min</span>
                        </div>
                        <div style={{ gridColumn: '1 / -1' }}>
                          <span className="h2g2-stat-label">O₂ estimado (simulado)</span>
                          <span className="h2g2-stat-value">{rotaAtiva.o2_estimado_l.toFixed(1)}L de {CAPACIDADE_O2_L_SIMULADA}L</span>
                          <div className="h2g2-progress" style={{ marginTop: 4 }}>
                            <div
                              className="h2g2-progress-fill"
                              style={{
                                width: `${Math.min(o2Pct, 100)}%`,
                                background: o2DentroDaReserva ? 'var(--verdict-seguro)' : 'var(--verdict-perigo)',
                              }}
                            />
                          </div>
                        </div>
                      </div>

                      <div className="h2g2-card" style={{ marginTop: 'var(--s-2)' }}>
                        <span className="h2g2-stat-label">Perfil de elevação</span>
                        <ElevationProfile perfil={rotaAtiva.perfil_elevacao} />
                      </div>
                    </div>
                  )
                })()}

              {data.avisos.length > 0 && avisoExpandido && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--s-2)' }}>
                    <p className="h2g2-panel-title" style={{ fontSize: 'var(--t-micro)' }}>
                      Avisos gerais da região
                    </p>
                    <button
                      onClick={() => setAvisoExpandido(false)}
                      className="h2g2-close-btn"
                      style={{ fontSize: 'var(--t-small)', padding: '0 var(--s-1)' }}
                      aria-label="Entendi, recolher avisos"
                    >
                      ×
                    </button>
                  </div>
                  {data.avisos.map((aviso, i) => (
                    <div
                      key={i}
                      className="h2g2-mono"
                      style={{
                        fontSize: 'var(--t-micro)',
                        color: SLOPE_VERDICT.atencao.color,
                        marginBottom: 'var(--s-2)',
                        lineHeight: 1.4,
                        overflowWrap: 'anywhere',
                      }}
                    >
                      ⚠ {aviso}
                    </div>
                  ))}
                </div>
              )}
              {data.avisos.length > 0 && !avisoExpandido && (
                <button
                  onClick={() => setAvisoExpandido(true)}
                  className="h2g2-mono h2g2-dim"
                  style={{ background: 'none', border: 'none', padding: 0, fontSize: 'var(--t-micro)', textDecoration: 'underline', cursor: 'pointer' }}
                >
                  ⚠ ver avisos gerais da região
                </button>
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
