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
        position: 'absolute',
        bottom: 'var(--s-4)',
        left: 'var(--s-4)',
        width: 240,
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
        <div className="h2g2-mono" style={{ fontSize: 'var(--t-small)', display: 'grid', gap: 'var(--s-1)' }}>
          <div>
            <span className="h2g2-dim">temp </span>
            {conditions.rems.temp_min_c}° a {conditions.rems.temp_max_c}°C
          </div>
          <div>
            <span className="h2g2-dim">pressão </span>
            {conditions.rems.pressao_pa} Pa
          </div>
          <div>
            <span className="h2g2-dim">UV pico </span>
            {conditions.rems.uv_pico} W/m²
          </div>
          <div>
            <span className="h2g2-dim">umidade </span>
            {conditions.rems.umidade_pct}%
          </div>
          <div style={{ borderTop: '1px solid var(--glass-rim)', paddingTop: 'var(--s-1)', marginTop: 'var(--s-1)' }}>
            <span className="h2g2-dim">dose RAD </span>
            <span style={{ color: 'var(--ember)' }}>{conditions.rad.dose_estimada_ugy_por_dia} µGy/dia</span>
          </div>
        </div>
      )}
    </div>
  )
}
