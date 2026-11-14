import type { ConditionsResponse } from '../api/types'

interface Props {
  conditions: ConditionsResponse | null
  error: string | null
}

/** Clima (REMS) + radiação (RAD) do sol de referência -- não depende
 * do ponto clicado (ver api/main.py: REFERENCE_SOL). Dado real
 * cacheado, não "ao vivo" -- rotulado como tal, sem fingir telemetria
 * em tempo real que não temos. */
export function ConditionsPanel({ conditions, error }: Props) {
  return (
    <div
      className="h2g2-panel"
      style={{
        // Parte do grupo flex-column em App.tsx (junto com
        // LayerControlPanel) -- não fica mais ancorado sozinho no
        // bottom, senão volta a cobrir o painel de cima se ele crescer.
        flex: 'none',
        width: '100%',
        padding: 'var(--s-3) var(--s-4)',
      }}
    >
      <p className="h2g2-panel-title">Condições · sol {conditions?.sol ?? '—'}</p>

      {error && (
        <div className="h2g2-dim h2g2-mono" style={{ fontSize: 'var(--t-small)' }}>
          indisponível
        </div>
      )}

      {!error && !conditions && (
        <div className="h2g2-dim h2g2-mono" style={{ fontSize: 'var(--t-small)' }}>
          carregando...
        </div>
      )}

      {conditions && (
        <div className="h2g2-card h2g2-stat-grid">
          <div>
            <span className="h2g2-stat-label">Temp</span>
            <span className="h2g2-stat-value" style={{ fontSize: 'var(--t-small)' }}>
              {conditions.rems.temp_min_c}° a {conditions.rems.temp_max_c}°C
            </span>
          </div>
          <div>
            <span className="h2g2-stat-label">Pressão</span>
            <span className="h2g2-stat-value" style={{ fontSize: 'var(--t-small)' }}>{conditions.rems.pressao_pa} Pa</span>
          </div>
          <div>
            <span className="h2g2-stat-label">UV pico</span>
            <span className="h2g2-stat-value" style={{ fontSize: 'var(--t-small)' }}>{conditions.rems.uv_pico} W/m²</span>
          </div>
          <div>
            <span className="h2g2-stat-label">Umidade</span>
            <span className="h2g2-stat-value" style={{ fontSize: 'var(--t-small)' }}>{conditions.rems.umidade_pct}%</span>
          </div>
          <div style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--glass-rim)', paddingTop: 'var(--s-2)' }}>
            <span className="h2g2-stat-label">Dose RAD</span>
            <span className="h2g2-stat-value" style={{ color: 'var(--ember)' }}>
              {conditions.rad.dose_estimada_ugy_por_dia} µGy/dia
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
