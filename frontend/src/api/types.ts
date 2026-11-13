/**
 * Espelha o JSON devolvido por `GET /api/point` em `api/main.py`.
 * Qualquer mudança de schema lá precisa ser refletida aqui -- é o
 * mesmo contrato que a feature 02 (rota) e a feature 08 (voz) vão
 * consumir, então mudar isso sem avisar o time quebra mais gente.
 */

export interface NearbyPhoto {
  distance_m: number
  bearing: string
  sol: number
  camera: string
  url: string
}

export interface ScienceTarget {
  nome: string | null
  mineral_crism: string | null
  classe_terreno: string | null
  medicao_curiosity: string | null
  confianca: string | null
  fonte: string | null
  distance_m: number
}

export type SlopeStatus = 'seguro' | 'atencao' | 'perigo'

export interface RasterValue {
  categoria: string
  valor: number
  slope_deg?: number
  slope_status?: SlopeStatus
}

export interface PointResponse {
  point: { lat: number; lon: number }
  nearby_photos: NearbyPhoto[]
  science_target: ScienceTarget | null
  raster_values: Record<string, RasterValue>
}

/** Espelha `GET /api/conditions` -- resumo de clima (REMS) e radiação
 * (RAD) de um sol de referência, não é por coordenada. */
export interface ConditionsResponse {
  sol: number
  rems: {
    temp_min_c: number | null
    temp_max_c: number | null
    pressao_pa: number | null
    uv_pico: number | null
    umidade_pct: number | null
    n_leituras: number
  }
  rad: {
    dose_media_ugy_por_hora: number | null
    dose_estimada_ugy_por_dia: number | null
    n_leituras: number
  }
}

/** Espelha `GET /api/nomenclature` -- feições com nome oficial
 * IAU/USGS na região de Gale. */
export interface NomenclatureFeature {
  nome: string
  tipo: string
  categoria_camada: string
  lat: number
  lon: number
  diametro_km: number
  aprovado_iau: string
  fonte_url: string
}

/** Espelha uma linha de `raster_registry`, devolvida por `GET /layers`. */
export interface LayerMeta {
  layer_name: string
  min_lon: number
  min_lat: number
  max_lon: number
  max_lat: number
  categoria: string
  tipo_acesso: 'raster_unico' | 'tiles_wmts'
}
