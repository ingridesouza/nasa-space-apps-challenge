import { LAYER_MAXZOOM } from '../map/style'

interface TopHudProps {
  lastClick: { lat: number; lon: number } | null
  sol: number | null
  zoom: number | null
}

/** Zoom real mais detalhado que baixamos (HiRISE, 18) -- além disso é
 * só upscale de pixel (borra), não tile novo carregando. Ver
 * LAYER_MAXZOOM em map/style.ts pro porquê desse número por camada. */
const ZOOM_REAL_MAXIMO = Math.max(...Object.values(LAYER_MAXZOOM))

export function TopHud({ lastClick, sol, zoom }: TopHudProps) {
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
          {zoom !== null && (
            <>
              <span className="h2g2-dim"> · zoom </span>
              <span style={{ color: zoom > ZOOM_REAL_MAXIMO ? 'var(--amber)' : 'var(--ink)' }}>{zoom.toFixed(1)}</span>
              {zoom > ZOOM_REAL_MAXIMO && (
                <span className="h2g2-dim" style={{ fontSize: 'var(--t-micro)' }}>
                  {' '}
                  (além do real, z{ZOOM_REAL_MAXIMO})
                </span>
              )}
            </>
          )}
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
