import type { ScienceTarget } from '../api/types'

interface Props {
  target: ScienceTarget | null
}

/** Feature 4 (Victoria): ficha científica do ponto. science_targets
 * está vazia até os 8-10 alvos serem estruturados (ver
 * PROXIMOS-PASSOS.md) -- mesma lógica do NearbyPhotosSection, estado
 * vazio real. */
export function ScienceTargetSection({ target }: Props) {
  return (
    <div style={{ marginTop: 'var(--s-4)' }}>
      <p className="h2g2-panel-title">Ficha científica</p>
      {target === null ? (
        <div className="h2g2-empty-state">Nenhum alvo científico cadastrado próximo deste ponto.</div>
      ) : (
        <div style={{ fontSize: 'var(--t-small)' }}>
          <div>
            <strong>{target.nome}</strong>
          </div>
          {target.medicao_curiosity && <div>{target.medicao_curiosity}</div>}
          {target.mineral_crism && <div className="h2g2-dim">CRISM: {target.mineral_crism}</div>}
          {target.classe_terreno && <div className="h2g2-dim">Terreno: {target.classe_terreno}</div>}
          {target.confianca && <div className="h2g2-dim">Confiança: {target.confianca}</div>}
        </div>
      )}
    </div>
  )
}
