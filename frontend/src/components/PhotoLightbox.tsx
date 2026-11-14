import type { CSSProperties } from 'react'
import { useEffect } from 'react'
import { createPortal } from 'react-dom'

export interface LightboxPhoto {
  url: string
  sol: number
  camera: string
  /** legenda extra opcional (distância/direção, quando vem de uma busca por raio) */
  caption?: string
}

interface PhotoLightboxProps {
  photos: LightboxPhoto[]
  index: number
  onClose: () => void
  onIndexChange: (index: number) => void
}

/** Lightbox único, reusado tanto pelo grid de "fotos próximas" quanto
 * pelos pins do "rastro do rover" -- eram duas implementações
 * duplicadas antes. Monta via portal pro document.body: dentro de um
 * painel com backdrop-filter, `position: fixed` vira relativo ao
 * painel, não à viewport (bug real encontrado e corrigido em
 * 2026-11-14).
 *
 * Tamanho de exibição fixo (`width: min(800px, 92vw)`) com
 * letterbox preto -- câmeras diferentes do Curiosity (Mastcam,
 * Navcam, Hazcam, MARDI) têm resoluções e proporções bem diferentes
 * de verdade (MARDI é fisheye circular, por exemplo -- não é bug,
 * é a câmera mesmo); sem isso, foto de baixa resolução aparecia
 * minúscula no meio da tela (só `max-width`/`max-height` não faz
 * imagem pequena crescer). */
export function PhotoLightbox({ photos, index, onClose, onIndexChange }: PhotoLightboxProps) {
  const foto = photos[index]

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowRight') onIndexChange((index + 1) % photos.length)
      if (e.key === 'ArrowLeft') onIndexChange((index - 1 + photos.length) % photos.length)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [index, photos.length, onClose, onIndexChange])

  if (!foto) return null

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(10, 10, 11, 0.9)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: 'var(--s-5)',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ position: 'relative', display: 'flex', alignItems: 'center', gap: 'var(--s-3)' }}
      >
        {photos.length > 1 && (
          <button
            onClick={() => onIndexChange((index - 1 + photos.length) % photos.length)}
            className="h2g2-mono"
            aria-label="Foto anterior"
            style={navButtonStyle}
          >
            ‹
          </button>
        )}

        <div
          style={{
            width: 'min(800px, 80vw)',
            height: 'min(600px, 70vh)',
            background: '#000',
            borderRadius: 'var(--r-2)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
            cursor: 'zoom-out',
          }}
        >
          <img
            src={foto.url}
            alt={`${foto.camera} · sol ${foto.sol}`}
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          />
        </div>

        {photos.length > 1 && (
          <button
            onClick={() => onIndexChange((index + 1) % photos.length)}
            className="h2g2-mono"
            aria-label="Próxima foto"
            style={navButtonStyle}
          >
            ›
          </button>
        )}
      </div>

      <div className="h2g2-mono" style={{ color: 'var(--ink-2)', fontSize: 'var(--t-small)', marginTop: 'var(--s-3)' }}>
        {foto.caption ? `${foto.caption} · ` : ''}
        sol {foto.sol} · {foto.camera}
        {photos.length > 1 && (
          <span className="h2g2-dim"> · {index + 1}/{photos.length}</span>
        )}
      </div>
    </div>,
    document.body,
  )
}

const navButtonStyle: CSSProperties = {
  background: 'rgba(255, 255, 255, 0.08)',
  border: '1px solid var(--glass-rim)',
  borderRadius: '50%',
  width: 40,
  height: 40,
  color: 'var(--ink)',
  fontSize: 22,
  lineHeight: 1,
  cursor: 'pointer',
  flex: 'none',
}
