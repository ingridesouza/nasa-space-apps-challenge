import type { NomenclatureFeature } from '../api/types'

const MARS_RADIUS_M = 3_396_190

function haversineM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(lon2 - lon1)
  const a =
    Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2
  return MARS_RADIUS_M * 2 * Math.asin(Math.sqrt(a))
}

/** Feição nomeada (IAU/USGS) mais próxima de um ponto -- cálculo client-side
 * porque a lista é pequena (13 feições na região de Gale), não precisa
 * de endpoint dedicado no backend. */
export function nearestNomenclature(
  features: NomenclatureFeature[],
  lat: number,
  lon: number,
): { feature: NomenclatureFeature; distance_m: number } | null {
  if (features.length === 0) return null

  let best = features[0]
  let bestDist = haversineM(lat, lon, best.lat, best.lon)

  for (const f of features.slice(1)) {
    const d = haversineM(lat, lon, f.lat, f.lon)
    if (d < bestDist) {
      best = f
      bestDist = d
    }
  }

  return { feature: best, distance_m: bestDist }
}
