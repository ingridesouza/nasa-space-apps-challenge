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

/** Posição atual do astronauta: rastreador simulado na base provisória. */
export const getPosicao = () => get('/api/posicao')
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
export const getLayers = () => get('/layers')
/** paradas: [{lat,lon}, ...] opcional, em ordem -- pontos entre origem e destino. */
export const getRoute = (o, d, paradas = []) => {
  const params = new URLSearchParams({ origin_lat: o.lat, origin_lon: o.lon, dest_lat: d.lat, dest_lon: d.lon })
  for (const p of paradas) {
    params.append('stop_lat', p.lat)
    params.append('stop_lon', p.lon)
  }
  return get(`/api/route?${params}`)
}
// F03/F04 (rotas do subprojeto servidas pela mesma API)
export const getPanorama = (lat, lon) => get(`/panoramas/nearest?lat=${lat}&lon=${lon}`)
export const getFotosPerto = (lat, lon) => get(`/photos/near?lat=${lat}&lon=${lon}`)
export const getFichaCientifica = (lat, lon) => get(`/science/card?lat=${lat}&lon=${lon}`)

/** F08 voz: áudio float32 mono 16 kHz → {texto, intencao, destino, origem, fala}. */
export async function enviarVoz(audio, { ativado, confirmando, lat, lon, idioma }) {
  const q = new URLSearchParams({ ativado, confirmando, ...(lat !== undefined && { lat, lon }), ...(idioma && { idioma }) })
  const resp = await fetch(`/api/voz?${q}`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: audio })
  const corpo = await resp.json().catch(() => null)
  if (!resp.ok) throw new Error(corpo?.detail ?? `/api/voz falhou: ${resp.status}`)
  return corpo
}

/** F08: pergunta ao agente local. 503 (modelo fora) traz detail={mensagem, alertas}. */
export async function perguntar(pergunta, lat, lon, rota = null, pos = null, idioma = null) { // sem lat/lon: a API usa a base
  const resp = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pergunta, ...(lat !== undefined && { lat, lon }), ...(rota && { rota }), ...(pos && { pos_lat: pos.lat, pos_lon: pos.lon }), ...(idioma && { idioma }) }),
  })
  const corpo = await resp.json().catch(() => null)
  if (!resp.ok) throw new Error(corpo?.detail?.mensagem ?? `/api/ask falhou: ${resp.status}`)
  return corpo
}
