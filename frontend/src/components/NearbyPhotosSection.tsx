import type { NearbyPhoto } from '../api/types'

interface Props {
  photos: NearbyPhoto[]
}

/** Feature 3 (Victoria): fotos do Curiosity num raio de ~200m. A
 * tabela rover_images está vazia até o item 9 do PROXIMOS-PASSOS.md
 * (API de imagens do MSL) ser resolvido -- por isso o estado vazio é
 * real, não um placeholder de "em breve" falso: a lógica de busca por
 * raio já funciona de verdade no backend, só falta o dado. */
export function NearbyPhotosSection({ photos }: Props) {
  return (
    <div style={{ marginTop: 'var(--s-4)' }}>
      <p className="h2g2-panel-title">Fotos próximas</p>
      {photos.length === 0 ? (
        <div className="h2g2-empty-state">Nenhuma foto cadastrada neste raio ainda.</div>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, fontSize: 'var(--t-small)' }}>
          {photos.map((p, i) => (
            <li key={i} className="h2g2-mono">
              {p.distance_m}m · {p.bearing} · sol {p.sol} · {p.camera}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
