import type { StyleSpecification } from 'maplibre-gl'

import { mosaicUrl } from '../api/client'
import type { LayerMeta } from '../api/types'
import { TOGGLEABLE_LAYERS } from './layers'

/** Bbox de teste usado em todo o pipeline (ver PROXIMOS-PASSOS.md) --
 * NÃO é o recorte final do boxwork, só o que já temos dado real
 * baixado pra exibir. Usado só como fallback de câmera inicial; o
 * bbox real de cada camada vem de `/layers`. */
export const TEST_BBOX_CENTER: [number, number] = [137.44, -4.59]

/** Começa no nível mais detalhado que baixamos (HiRISE) -- é a
 * primeira coisa que o usuário deve ver. Dar zoom OUT revela o CTX
 * (a camada de menor resolução, sempre por baixo) cobrindo uma área
 * um pouco maior. */
export const TEST_BBOX_INITIAL_ZOOM = 15

/** Converte o bbox retangular (min/max lon/lat) nas 4 coordenadas de
 * canto que o `ImageSource` do MapLibre espera: topo-esquerda,
 * topo-direita, baixo-direita, baixo-esquerda. */
function bboxToCorners(meta: LayerMeta): [[number, number], [number, number], [number, number], [number, number]] {
  return [
    [meta.min_lon, meta.max_lat],
    [meta.max_lon, meta.max_lat],
    [meta.max_lon, meta.min_lat],
    [meta.min_lon, meta.min_lat],
  ]
}

export function buildStyle(layersMeta: LayerMeta[]): StyleSpecification {
  const metaByName = Object.fromEntries(layersMeta.map((m) => [m.layer_name, m]))

  const sources: StyleSpecification['sources'] = {}
  const layers: StyleSpecification['layers'] = [
    {
      id: 'background',
      type: 'background',
      paint: { 'background-color': '#05070a' },
    },
  ]

  // Ordem de TOGGLEABLE_LAYERS = ordem de desenho: a última da lista
  // fica por cima. Cada camada já nasce com toggle+opacidade (spec da
  // feature 01: "cada camada liga, desliga e tem opacidade ajustável").
  for (const layer of TOGGLEABLE_LAYERS) {
    const meta = metaByName[layer.id]
    if (!meta) continue // camada ainda não confirmada/populada no backend

    sources[layer.id] = {
      type: 'image',
      url: mosaicUrl(layer.id),
      coordinates: bboxToCorners(meta),
    }
    layers.push({
      id: layer.id,
      type: 'raster',
      source: layer.id,
      layout: { visibility: layer.defaultVisible ? 'visible' : 'none' },
      paint: { 'raster-opacity': layer.defaultOpacity },
    })
  }

  return {
    version: 8,
    sources,
    layers,
  }
}
