// Local API client -- same origin (the API serves this web/), no external URL.
// JSON contract: see api/main.py (formerly mirrored in frontend/src/api/types.ts).

async function get(path) {
  const resp = await fetch(path)
  if (!resp.ok) {
    const body = await resp.json().catch(() => null)
    throw new Error(body?.detail ?? `${path.split('?')[0]} failed: ${resp.status}`)
  }
  return resp.json()
}

/** Current astronaut position: simulated tracker at the provisional base. */
export const getPosition = () => get('/api/position')
export const getPoint = (lat, lon) => get(`/api/point?lat=${lat}&lon=${lon}`)
export const getConditions = (sol) => get(`/api/conditions${sol ? `?sol=${sol}` : ''}`)
/** F09 (simulated): is a real, pre-fetched Earth packet waiting to be revealed? No network call. */
export const getEarthSyncStatus = () => get('/api/earth-sync/status')
/** F09 (simulated): reveal the waiting packet locally -- see docs/feature-09-earth-mars-sync.md. */
export const applyEarthSync = () => fetch('/api/earth-sync/apply', { method: 'POST' }).then((r) => r.json())
/** F06: habitat/suit sensor measurement. 422 carries detail (text or pydantic list). */
export async function postMeasurement(m) {
  const resp = await fetch('/api/measurement', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(m) })
  const body = await resp.json().catch(() => null)
  if (!resp.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : 'measurement outside the physical range of Gale')
  return body
}
export const deleteMeasurement = (sol) => fetch(`/api/measurement/${sol}`, { method: 'DELETE' })

/** F06. q optional: {sol, duration_min}. */
export const getForecast = (q = {}) => get(`/api/forecast?${new URLSearchParams(q)}`)
export const getNomenclature = () => get('/api/nomenclature')
export const getLayers = () => get('/layers')
/** Atmospheric layer: GeoJSON, one point per sol measured by REMS. */
export const getAtmosphereTrack = () => get('/api/atmosphere/track')
/** Sun position and max direct irradiance for the local solar hour (current sol). */
export const getInsolation = (hour, point = null) => get(`/api/insolation?${new URLSearchParams({ hour, ...(point && { lat: point.lat, lon: point.lon }) })}`)
/** Simulated mission clock: {sol, lmst, ltst} (local solar time at Gale). */
export const getClock = () => get('/api/clock')
/** stops: [{lat,lon}, ...] optional, in order -- points between origin and destination. */
export const getRoute = (o, d, stops = []) => {
  const params = new URLSearchParams({ origin_lat: o.lat, origin_lon: o.lon, dest_lat: d.lat, dest_lon: d.lon })
  for (const p of stops) {
    params.append('stop_lat', p.lat)
    params.append('stop_lon', p.lon)
  }
  return get(`/api/route?${params}`)
}
// F03/F04 (subproject routes served by the same API)
export const getPanorama = (lat, lon) => get(`/panoramas/nearest?lat=${lat}&lon=${lon}`)
export const getPhotosNear = (lat, lon) => get(`/photos/near?lat=${lat}&lon=${lon}`)
export const getScienceCard = (lat, lon) => get(`/science/card?lat=${lat}&lon=${lon}`)

/** F08 voice: float32 mono 16 kHz audio → {text, intent, destination, origin, speech}. */
export async function sendVoice(audio, { activated, confirming, lat, lon, openBlocks = [], focus = null }) {
  const q = new URLSearchParams({ activated, confirming, open_blocks: openBlocks.join(','), ...(focus && { focus }), ...(lat !== undefined && { lat, lon }) })
  const resp = await fetch(`/api/voice?${q}`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: audio })
  const body = await resp.json().catch(() => null)
  if (!resp.ok) throw new Error(body?.detail ?? `/api/voice failed: ${resp.status}`)
  return body
}

/** F08: question to the local agent. 503 (model down) carries detail={message, alerts}. */
export async function ask(question, lat, lon, route = null, pos = null) { // without lat/lon: the API uses the base
  const resp = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, ...(lat !== undefined && { lat, lon }), ...(route && { route }),
      ...(pos && { pos_lat: pos.lat, pos_lon: pos.lon }) }),
  })
  const body = await resp.json().catch(() => null)
  if (!resp.ok) {
    // model down (503): the rule-built answer card still comes in detail.card
    throw Object.assign(new Error(body?.detail?.message ?? `/api/ask failed: ${resp.status}`), { card: body?.detail?.card })
  }
  return body
}
