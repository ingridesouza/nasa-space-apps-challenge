/**
 * Config das camadas do mapa -- espelha (sem ser gerado automaticamente
 * de) `data-pipeline/config/layers.yaml`. Se uma camada nova for
 * confirmada lá, ela precisa ganhar uma entrada aqui também. O bbox
 * real de cada uma vem do backend (`GET /layers`), não daqui -- isto
 * só decide ordem/agrupamento/rótulo/estado inicial na UI.
 */

export interface ToggleableLayerConfig {
  id: string
  label: string
  grupo: 'base' | 'overlay'
  defaultVisible: boolean
  defaultOpacity: number
}

export interface PlannedLayerConfig {
  id: string
  label: string
  motivo: string
  /** 'em_breve': falta trabalho nosso. 'fora_de_escopo': decisão já
   * tomada de não incluir -- a spec da feature 01 pede pra "dizer isso
   * com clareza" em vez de simplesmente omitir a camada. */
  status: 'em_breve' | 'fora_de_escopo'
}

/** Toda camada real (confirmada no backend) que aparece no mapa --
 * cada uma liga/desliga e tem opacidade ajustável, como a spec da
 * feature 01 pede ("cada camada"). A ordem aqui é a ordem de desenho:
 * a última aparece por cima das anteriores. */
export const TOGGLEABLE_LAYERS: ToggleableLayerConfig[] = [
  { id: 'ctx_optica', label: 'CTX (contexto, ~6m)', grupo: 'base', defaultVisible: true, defaultOpacity: 1 },
  { id: 'hirise_optica', label: 'HiRISE (detalhe, 25cm)', grupo: 'base', defaultVisible: true, defaultOpacity: 1 },
  {
    id: 'relevo_hillshade',
    label: 'Relevo (hillshade do DTM)',
    grupo: 'overlay',
    defaultVisible: false,
    defaultOpacity: 0.7,
  },
  { id: 'themis_termica', label: 'Térmica (THEMIS)', grupo: 'overlay', defaultVisible: false, defaultOpacity: 0.6 },
]

/** Camadas que não têm pirâmide visual ainda, ou que foram
 * deliberadamente deixadas fora do escopo. Mostrar isso explicitamente
 * é mais honesto que esconder ou fingir que existe (e, no caso da
 * geofísica, é a própria spec que pede pra comunicar isso com clareza
 * em vez de só omitir a camada). */
export const PLANNED_LAYERS: PlannedLayerConfig[] = [
  { id: 'mineralogia', label: 'Mineralogia (CRISM)', motivo: 'cobertura esparsa em Gale, ver PROXIMOS-PASSOS.md', status: 'em_breve' },
  {
    id: 'geofisica',
    label: 'Geofísica',
    motivo: 'sem dado orbital útil na escala de metros do boxwork -- decisão de escopo, não pendência',
    status: 'fora_de_escopo',
  },
]
