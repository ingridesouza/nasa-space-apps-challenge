import { useState } from 'react'

import type { NearbyPhoto } from '../api/types'
import { PhotoLightbox } from './PhotoLightbox'

interface Props {
  photos: NearbyPhoto[]
}

/** Feature 3 (Victoria): fotos reais do Curiosity num raio de ~200m,
 * em ordem de distância (já vem ordenado do backend). Grid clicável
 * com lightbox -- spec da feature 01 (seção 4) pede explicitamente
 * "grid/lightbox de fotos estáticas, ordenadas por distância e
 * direção", não só uma lista de texto. */
export function NearbyPhotosSection({ photos }: Props) {
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)

  return (
    <div style={{ marginTop: 'var(--s-4)' }}>
      <p className="h2g2-panel-title">Fotos próximas</p>
      {photos.length === 0 ? (
        <div className="h2g2-empty-state">Nenhuma foto cadastrada neste raio ainda.</div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: 'var(--s-2)',
          }}
        >
          {photos.map((p, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setLightboxIndex(i)}
              style={{
                padding: 0,
                border: '1px solid var(--glass-rim)',
                borderRadius: 'var(--r-2)',
                background: 'var(--n900)',
                cursor: 'pointer',
                overflow: 'hidden',
                textAlign: 'left',
              }}
            >
              <img
                src={p.url}
                alt={`${p.camera} · sol ${p.sol}`}
                loading="lazy"
                style={{ width: '100%', aspectRatio: '4 / 3', objectFit: 'cover', display: 'block' }}
              />
              <div className="h2g2-mono h2g2-dim" style={{ fontSize: 'var(--t-micro)', padding: '4px 6px' }}>
                {p.distance_m}m · {p.bearing} · sol {p.sol}
              </div>
            </button>
          ))}
        </div>
      )}

      {lightboxIndex !== null && (
        <PhotoLightbox
          photos={photos.map((p) => ({ url: p.url, sol: p.sol, camera: p.camera, caption: `${p.distance_m}m · ${p.bearing}` }))}
          index={lightboxIndex}
          onClose={() => setLightboxIndex(null)}
          onIndexChange={setLightboxIndex}
        />
      )}
    </div>
  )
}
