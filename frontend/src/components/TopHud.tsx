interface TopHudProps {
  lastClick: { lat: number; lon: number } | null
  sol: number | null
}

export function TopHud({ lastClick, sol }: TopHudProps) {
  return (
    <div
      className="h2g2-panel"
      style={{
        position: 'absolute',
        top: 'var(--s-4)',
        left: 'var(--s-4)',
        right: 'var(--s-4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: 'var(--s-3) var(--s-4)',
        pointerEvents: 'none',
      }}
    >
      <div>
        <div className="h2g2-display" style={{ fontSize: 'var(--t-4)', color: 'var(--ink)', lineHeight: 1.1 }}>
          H2G2 <span style={{ color: 'var(--mars2)' }}>·</span> Mapa hiperlocal do boxwork
        </div>
        <div className="h2g2-dim h2g2-mono" style={{ fontSize: 'var(--t-micro)', letterSpacing: '0.08em' }}>
          CRATERA GALE · MONTE SHARP
        </div>
      </div>

      <div className="h2g2-mono" style={{ fontSize: 'var(--t-small)', textAlign: 'right' }}>
        <div>
          <span className="h2g2-dim">sol </span>
          <span>{sol ?? '—'}</span>
        </div>
        <div>
          {lastClick ? (
            <span style={{ color: 'var(--hud-cyan)' }}>
              {lastClick.lat.toFixed(5)}, {lastClick.lon.toFixed(5)}
            </span>
          ) : (
            <span className="h2g2-dim">clique no mapa</span>
          )}
        </div>
      </div>
    </div>
  )
}
