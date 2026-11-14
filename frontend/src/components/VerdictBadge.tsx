import type { SlopeStatus } from '../api/types'
import { SLOPE_VERDICT } from '../theme/verdict'

export interface ChecklistItem {
  ok: boolean
  label: string
}

interface VerdictBadgeProps {
  status: SlopeStatus
  checklist?: ChecklistItem[]
}

/** Veredito grande e imediato (padrão "GO/NO-GO"), extraído de
 * PointInfoPanel e RoutePanel que tinham a mesma lógica duplicada
 * inline. Usa SLOPE_VERDICT (theme/verdict.ts) -- mesma cor/limite de
 * 20° já usado em todo o sistema, não inventa nada novo. */
export function VerdictBadge({ status, checklist }: VerdictBadgeProps) {
  const veredito = SLOPE_VERDICT[status]

  return (
    <div
      style={{
        border: `1px solid ${veredito.color}`,
        borderRadius: 'var(--r-2)',
        padding: 'var(--s-3)',
        background: `color-mix(in srgb, ${veredito.color} 10%, transparent)`,
      }}
    >
      <div
        className="h2g2-display"
        style={{
          color: veredito.color,
          fontSize: 'var(--t-4)',
          fontWeight: 700,
          lineHeight: 1.25,
          display: 'flex',
          alignItems: 'flex-start',
          gap: 'var(--s-2)',
        }}
      >
        <span style={{ fontSize: '0.8em', lineHeight: 'inherit' }}>●</span>
        {veredito.label}
      </div>

      {checklist && checklist.length > 0 && (
        <div style={{ marginTop: 'var(--s-2)', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {checklist.map((item, i) => (
            <div
              key={i}
              className="h2g2-mono"
              style={{ fontSize: 'var(--t-small)', color: item.ok ? 'var(--ink-2)' : veredito.color }}
            >
              {item.ok ? '✓' : '⚠'} {item.label}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
