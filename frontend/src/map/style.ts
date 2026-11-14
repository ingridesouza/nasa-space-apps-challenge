import type { StyleSpecification } from 'maplibre-gl'

import { API_BASE_URL } from '../api/client'
import type { LayerMeta } from '../api/types'
import { TOGGLEABLE_LAYERS } from './layers'

/** Bbox REAL da campanha de boxwork (sol ~4500-4684), confirmado em
 * 2026-11-13 via MSL_waypoints.json (MMGIS oficial) -- ver
 * PROXIMOS-PASSOS.md. Usado só como fallback de câmera inicial; o
 * bbox real de cada camada vem de `/layers`. */
export const TEST_BBOX_CENTER: [number, number] = [137.384, -4.801]

/** Começa no nível mais detalhado que baixamos (HiRISE) -- é a
 * primeira coisa que o usuário deve ver. Dar zoom OUT revela o CTX
 * (a camada de menor resolução, sempre por baixo) cobrindo uma área
 * um pouco maior. */
export const TEST_BBOX_INITIAL_ZOOM = 15

/** zoom máximo "real" de cada camada -- calculado da resolução de
 * pixel de verdade (m/px) usando o raio de Marte (não o da Terra),
 * pra MapLibre começar a borrar (overzoom) só além do que realmente
 * baixamos, sem fingir mais precisão do que existe. Ver
 * api/tile_server.py pro porquê o endereçamento z/x/y funciona sem
 * reprojeção cartográfica de verdade. */
export const LAYER_MAXZOOM: Record<string, number> = {
  hirise_optica: 18, // ~25cm/px declarado
  relevo_hillshade: 14, // ~5.88m/px real do DTM
  ctx_optica: 14, // ~6m/px declarado
  themis_termica: 10, // ~100m/px declarado
}

/** União do bbox de todas as camadas raster reais -- usado como
 * `maxBounds` do mapa. Antes da correção de georreferenciamento
 * (2026-11-14), todo layer tinha o MESMO bbox declarado (errado), então
 * dava pra navegar livre sem perceber; agora que cada camada tem seu
 * bbox real (CTX/HiRISE/THEMIS com extensões diferentes entre si), dar
 * zoom out ou pan além da cobertura real mostra só vazio escuro -- o
 * que é honesto, mas confunde ("por que ficou assim?"). Travar a câmera
 * nessa união evita cair no vazio sem nem perceber que saiu da área com
 * dado baixado. */
export function dataBounds(layersMeta: LayerMeta[]): [[number, number], [number, number]] | null {
  if (layersMeta.length === 0) return null
  const minLon = Math.min(...layersMeta.map((m) => m.min_lon))
  const minLat = Math.min(...layersMeta.map((m) => m.min_lat))
  const maxLon = Math.max(...layersMeta.map((m) => m.max_lon))
  const maxLat = Math.max(...layersMeta.map((m) => m.max_lat))
  // pequena folga (10%) pra não travar bem na borda da imagem
  const padLon = (maxLon - minLon) * 0.1
  const padLat = (maxLat - minLat) * 0.1
  return [
    [minLon - padLon, minLat - padLat],
    [maxLon + padLon, maxLat + padLat],
  ]
}

/** Bbox só das camadas "base" (CTX/HiRISE, sempre visíveis por
 * padrão) -- usado pro cálculo de zoom mínimo abaixo. Não usa a união
 * com TODAS as camadas (ver `dataBounds`) porque o THEMIS tem bbox bem
 * mais largo (menor resolução, menos tiles cobrem mais área) e fica
 * desligado por padrão -- se o "chão" de zoom out fosse calculado pra
 * caber o THEMIS, CTX/HiRISE (o que realmente está visível na maioria
 * do tempo) ainda apareceria pequeno demais no viewport. */
export function baseLayersBounds(layersMeta: LayerMeta[]): [[number, number], [number, number]] | null {
  const idsBase = new Set(TOGGLEABLE_LAYERS.filter((l) => l.grupo === 'base').map((l) => l.id))
  return dataBounds(layersMeta.filter((m) => idsBase.has(m.layer_name)))
}

/** Zoom mínimo pra garantir que a cobertura das camadas base (ver
 * `baseLayersBounds`) sempre preencha o viewport inteiro -- sem isso, dar zoom out revela
 * o retângulo de dado real "flutuando" numa tela toda preta (bug
 * reportado pelo usuário: "parece mapa quebrado"). `maxBounds` só
 * trava o PAN; sem travar o zoom OUT também, dava pra ver a área real
 * ficar pequena demais pro viewport.
 *
 * Mesma matemática de tile 256px/zoom usada em api/tile_server.py
 * (pixels por grau = 2^z * 256 / 360) -- pega o maior z exigido entre
 * largura e altura, pra cobrir os dois eixos (igual `background-size:
 * cover`, nunca deixa borda vazia em nenhum dos dois). */
export function minZoomToCover(
  bounds: [[number, number], [number, number]],
  viewportWidthPx: number,
  viewportHeightPx: number,
): number {
  const [[minLon, minLat], [maxLon, maxLat]] = bounds
  const lonSpan = maxLon - minLon
  const latSpan = maxLat - minLat

  const zParaLargura = Math.log2((viewportWidthPx * 360) / (256 * lonSpan))
  const zParaAltura = Math.log2((viewportHeightPx * 360) / (256 * latSpan))
  return Math.max(zParaLargura, zParaAltura)
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
      type: 'raster',
      tiles: [`${API_BASE_URL}/tiles/${layer.id}/{z}/{x}/{y}.png`],
      tileSize: 256,
      minzoom: 0,
      maxzoom: LAYER_MAXZOOM[layer.id] ?? 18,
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
