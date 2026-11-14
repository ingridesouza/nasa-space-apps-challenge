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
/** F06: medição do sensor do habitat/traje. 422 traz detail (texto ou lista do pydantic). */
export async function postMedicao(m) {
  const resp = await fetch('/api/medicao', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(m) })
  const corpo = await resp.json().catch(() => null)
  if (!resp.ok) throw new Error(typeof corpo?.detail === 'string' ? corpo.detail : 'medição fora da faixa física de Gale')
  return corpo
}
export const apagarMedicao = (sol) => fetch(`/api/medicao/${sol}`, { method: 'DELETE' })

/** F06. q opcional: {sol, duracao_min}. */
export const getPrevisao = (q = {}) => get(`/api/previsao?${new URLSearchParams(q)}`)
export const getNomenclature = () => get('/api/nomenclature')
export const getRoverTrack = () => get('/api/rover-track')
export const getLayers = () => get('/layers')
export const getRoverPhotos = () => get('/api/photos')
export const getRoute = (o, d) =>
  get(`/api/route?origin_lat=${o.lat}&origin_lon=${o.lon}&dest_lat=${d.lat}&dest_lon=${d.lon}`)
export const mosaicUrl = (layer) => `/mosaics/${layer}.png`
// F03/F04 (rotas do subprojeto servidas pela mesma API)
export const getPanorama = (lat, lon) => get(`/panoramas/nearest?lat=${lat}&lon=${lon}`)
export const getFichaCientifica = (lat, lon) => get(`/science/card?lat=${lat}&lon=${lon}`)

/** F08: pergunta ao agente local. 503 (modelo fora) traz detail={mensagem, alertas}. */
export async function perguntar(pergunta, lat, lon) { // sem lat/lon: a API usa a base
  const resp = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(lat === undefined ? { pergunta } : { pergunta, lat, lon }),
  })
  const corpo = await resp.json().catch(() => null)
  if (!resp.ok) throw new Error(corpo?.detail?.mensagem ?? `/api/ask falhou: ${resp.status}`)
  return corpo
}
