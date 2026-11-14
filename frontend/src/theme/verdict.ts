import type { SlopeStatus } from '../api/types'

/** Limite de 20° citado no doc da feature 01 -- mesmo limite de
 * caminhada usado pelo programa Artemis (ver api/raster_sampling.py,
 * onde isso é calculado de verdade a partir do DTM/MOLA). */
export const SLOPE_VERDICT: Record<SlopeStatus, { color: string; label: string }> = {
  seguro: { color: 'var(--verdict-seguro)', label: 'Seguro pra caminhar' },
  atencao: { color: 'var(--verdict-atencao)', label: 'Atenção: declive acentuado' },
  perigo: { color: 'var(--verdict-perigo)', label: 'Perigo: acima do limite Artemis (20°)' },
}

/** Mesmas cores de SLOPE_VERDICT, em hex -- MapLibre pinta via WebGL,
 * não resolve var() de CSS custom properties, então o trecho da rota
 * no mapa precisa do valor literal (tem que bater com tokens.css
 * --verdict-seguro/--verdict-atencao/--verdict-perigo se eles mudarem). */
export const SLOPE_COLOR_HEX: Record<SlopeStatus, string> = {
  seguro: '#7fe0a8',
  atencao: '#f2b33d',
  perigo: '#e8643f',
}
