import type { SlopeStatus } from '../api/types'

/** Limite de 20° citado no doc da feature 01 -- mesmo limite de
 * caminhada usado pelo programa Artemis (ver api/raster_sampling.py,
 * onde isso é calculado de verdade a partir do DTM/MOLA). */
/** Mesmas cores de `--verdict-*` em `tokens.css`, em hex: o MapLibre
 * não lê variáveis CSS (usado pela trilha do Curiosity no mapa). */
export const SLOPE_HEX: Record<SlopeStatus, string> = {
  seguro: '#7fe0a8',
  atencao: '#f2b33d',
  perigo: '#e8643f',
}

export const SLOPE_VERDICT: Record<SlopeStatus, { color: string; label: string }> = {
  seguro: { color: 'var(--verdict-seguro)', label: 'Seguro pra caminhar' },
  atencao: { color: 'var(--verdict-atencao)', label: 'Atenção: declive acentuado' },
  perigo: { color: 'var(--verdict-perigo)', label: 'Perigo: acima do limite Artemis (20°)' },
}
