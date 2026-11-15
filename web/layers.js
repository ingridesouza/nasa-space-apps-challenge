/**
 * Config das camadas do mapa -- espelha (sem ser gerado de)
 * `data-pipeline/config/layers.yaml`. O bbox real de cada uma vem de
 * `GET /layers`; isto só decide ordem/agrupamento/rótulo/estado inicial.
 * Ordem = ordem de desenho: a última fica por cima.
 */
export const TOGGLEABLE_LAYERS = [
  { id: 'ctx_optica', label: 'CTX (contexto, ~10 m)', grupo: 'base', defaultVisible: true, defaultOpacity: 1 },
  { id: 'hirise_optica', label: 'HiRISE (detalhe, ~0,6 m)', grupo: 'base', defaultVisible: true, defaultOpacity: 1 },
  { id: 'relevo_hillshade', label: 'Relevo (hillshade do DTM)', grupo: 'overlay', defaultVisible: false, defaultOpacity: 0.7 },
  { id: 'themis_termica', label: 'Térmica (THEMIS, ~100 m/px)', grupo: 'overlay', defaultVisible: false, defaultOpacity: 0.6 },
  { id: 'risco_previsto', label: 'Risco de inclinação (previsto)', grupo: 'overlay', defaultVisible: false, defaultOpacity: 0.85 },
]

/** Camadas sem pirâmide visual ainda, ou deliberadamente fora do escopo --
 * mostrar isso é mais honesto que esconder (spec da feature 01). */
export const PLANNED_LAYERS = [
  { id: 'mineralogia', label: 'Mineralogia (CRISM)', motivo: 'cobertura esparsa em Gale, ver PROXIMOS-PASSOS.md', status: 'em_breve' },
  {
    id: 'geofisica',
    label: 'Geofísica',
    motivo: 'sem dado orbital útil na escala de metros do boxwork -- decisão de escopo, não pendência',
    status: 'fora_de_escopo',
  },
]

/** zoom máximo "real" de cada camada, da resolução de pixel (raio de
 * Marte) -- além disso é só overzoom (borra). Ver api/tile_server.py. */
export const LAYER_MAXZOOM = {
  hirise_optica: 17, // ~0,64 m/px nos tiles locais (z16 do Mars Trek); o produto tem 25 cm, não baixado
  relevo_hillshade: 14, // ~5.88m/px real do DTM
  ctx_optica: 13, // ~10,2 m/px nos tiles locais (z12 do Mars Trek); o produto tem ~6 m, não baixado
  themis_termica: 10, // ~100m/px declarado
  risco_previsto: 17, // mesmo DTM; cor por faixa (nearest), não borra
}

/** Limite de 20° (Artemis) -- ver api/raster_sampling.py. */
export const SLOPE_VERDICT = {
  seguro: { color: 'var(--verdict-seguro)', label: 'Seguro pra caminhar' },
  atencao: { color: 'var(--verdict-atencao)', label: 'Atenção: declive acentuado' },
  perigo: { color: 'var(--verdict-perigo)', label: 'Perigo: acima do limite Artemis (20°)' },
}

/** Mesmas cores em hex -- MapLibre pinta via WebGL e não resolve var()
 * (tem que bater com --verdict-* em style.css). */
export const SLOPE_COLOR_HEX = { seguro: '#7fe0a8', atencao: '#f2b33d', perigo: '#e8643f' }
