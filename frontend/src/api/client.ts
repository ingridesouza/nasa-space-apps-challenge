import type {
  ConditionsResponse,
  LayerMeta,
  NomenclatureFeature,
  PointResponse,
  RoverPhotoPin,
  RouteResponse,
  RoverStop,
} from './types'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export async function getPoint(lat: number, lon: number): Promise<PointResponse> {
  const url = `${API_BASE_URL}/api/point?lat=${lat}&lon=${lon}`
  const resp = await fetch(url)
  if (!resp.ok) {
    throw new Error(`/api/point falhou: ${resp.status}`)
  }
  return resp.json()
}

export async function getConditions(sol?: number): Promise<ConditionsResponse> {
  const qs = sol !== undefined ? `?sol=${sol}` : ''
  const resp = await fetch(`${API_BASE_URL}/api/conditions${qs}`)
  if (!resp.ok) {
    throw new Error(`/api/conditions falhou: ${resp.status}`)
  }
  return resp.json()
}

export async function getNomenclature(): Promise<NomenclatureFeature[]> {
  const resp = await fetch(`${API_BASE_URL}/api/nomenclature`)
  if (!resp.ok) {
    throw new Error(`/api/nomenclature falhou: ${resp.status}`)
  }
  return resp.json()
}

export async function getRoverTrack(): Promise<RoverStop[]> {
  const resp = await fetch(`${API_BASE_URL}/api/rover-track`)
  if (!resp.ok) {
    throw new Error(`/api/rover-track falhou: ${resp.status}`)
  }
  return resp.json()
}

export async function getLayers(): Promise<LayerMeta[]> {
  const resp = await fetch(`${API_BASE_URL}/layers`)
  if (!resp.ok) {
    throw new Error(`/layers falhou: ${resp.status}`)
  }
  return resp.json()
}

export async function getRoverPhotos(): Promise<RoverPhotoPin[]> {
  const resp = await fetch(`${API_BASE_URL}/api/photos`)
  if (!resp.ok) {
    throw new Error(`/api/photos falhou: ${resp.status}`)
  }
  return resp.json()
}

export async function getRoute(
  originLat: number,
  originLon: number,
  destLat: number,
  destLon: number,
): Promise<RouteResponse> {
  const url =
    `${API_BASE_URL}/api/route?origin_lat=${originLat}&origin_lon=${originLon}` +
    `&dest_lat=${destLat}&dest_lon=${destLon}`
  const resp = await fetch(url)
  if (!resp.ok) {
    const body = await resp.json().catch(() => null)
    throw new Error(body?.detail ?? `/api/route falhou: ${resp.status}`)
  }
  return resp.json()
}

/** Mosaico único das tiles de uma camada `tiles_wmts` -- não é mais um
 * template XYZ do MapLibre (ver api/mosaics.py pra entender por que
 * isso mudou: a grade de tiles do Mars Trek não é Web Mercator). */
export function mosaicUrl(layerName: string): string {
  return `${API_BASE_URL}/mosaics/${layerName}.png`
}
