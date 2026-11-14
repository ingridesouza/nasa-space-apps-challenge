// Cliente da API local -- mesma origem (a API serve este web/), sem URL externa.
// Contrato dos JSONs: ver api/main.py (antes espelhado em frontend/src/api/types.ts).

async function get(caminho) {
  const resp = await fetch(caminho)
  if (!resp.ok) {
    const corpo = await resp.json().catch(() => null)
    throw new Error(corpo?.detail ?? `${caminho.split('?')[0]} falhou: ${resp.status}`)
  }
  return resp.json()
}

export const getPoint = (lat, lon) => get(`/api/point?lat=${lat}&lon=${lon}`)
export const getConditions = () => get('/api/conditions')
export const getNomenclature = () => get('/api/nomenclature')
export const getRoverTrack = () => get('/api/rover-track')
export const getLayers = () => get('/layers')
export const getRoverPhotos = () => get('/api/photos')
export const getRoute = (o, d) =>
  get(`/api/route?origin_lat=${o.lat}&origin_lon=${o.lon}&dest_lat=${d.lat}&dest_lon=${d.lon}`)
export const mosaicUrl = (layer) => `/mosaics/${layer}.png`
