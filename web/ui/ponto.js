// Briefing de segurança do ponto clicado (antes PointInfoPanel + NearbyPhotosSection
// + ScienceTargetSection).
import { getPoint } from '../api.js'
import { abrirLightbox } from './lightbox.js'
import { coord, esc, nomeMaisProximo, veredito } from './util.js'

/** Alertas da feature 08 (api/alertas.py): mesmas cores do veredito. */
const ALERTA_COR = { perigo: 'var(--verdict-perigo)', atencao: 'var(--verdict-atencao)', info: 'var(--ink-3)' }

const CATEGORIA_LABEL = { topografica: 'Topografia', optica: 'Óptica', termica: 'Térmica', espectral_quimica: 'Mineralogia' }

/** Camada que virou o elevacao_m "oficial" (PRIORIDADE_ELEVACAO em api/raster_sampling.py). */
function camadaPrincipal(fontes) {
  if ('dtm_hirise_1m' in fontes) return 'dtm_hirise_1m'
  if ('mola_topografia_regional' in fontes) return 'mola_topografia_regional'
  return Object.keys(fontes)[0] ?? null
}

function secaoElevacao(rv) {
  const camada = camadaPrincipal(rv.fontes)
  const principal =
    rv.elevacao_m === null
      ? '<div class="h2g2-empty-state">Fora da área de teste com dado baixado (ver PROXIMOS-PASSOS.md).</div>'
      : `<div class="h2g2-bloco">
          ${rv.slope_status ? veredito(rv.slope_status) : ''}
          <div class="h2g2-card" style="margin-top:var(--s-2)">
            <div class="h2g2-display h2g2-elev">${rv.elevacao_m.toFixed(1)}<span class="h2g2-mono h2g2-small h2g2-dim"> m</span></div>
            ${rv.slope_deg !== null ? `<div class="h2g2-dim h2g2-mono h2g2-small">slope ${rv.slope_deg.toFixed(2)}°</div>` : ''}
            <div class="h2g2-dim h2g2-micro" style="margin-top:var(--s-1)">
              ${esc(CATEGORIA_LABEL[rv.fontes[camada]?.categoria] ?? rv.fontes[camada]?.categoria ?? '')} · ${esc(camada)}
            </div>
          </div>
        </div>`
  const outras = Object.entries(rv.fontes).filter(([nome]) => nome !== camada)
  if (outras.length === 0) return principal
  return `${principal}
    <div class="h2g2-bloco">
      <p class="h2g2-panel-title">Outras fontes de elevação</p>
      ${outras.map(([nome, v]) => `<div class="h2g2-dim h2g2-mono h2g2-small">${esc(nome)}: ${v.valor.toFixed(1)}m${v.slope_deg !== undefined ? ` · ${v.slope_deg.toFixed(2)}°` : ''}</div>`).join('')}
    </div>`
}

function secaoFotos(fotos) {
  const corpo = fotos.length === 0
    ? '<div class="h2g2-empty-state">Nenhuma foto cadastrada neste raio ainda.</div>'
    : `<div class="h2g2-fotos">${fotos.map((p, i) => `
        <button type="button" class="h2g2-foto" data-foto="${i}">
          <img src="${esc(p.url)}" alt="${esc(p.camera)} · sol ${esc(p.sol)}" loading="lazy">
          <div class="h2g2-mono h2g2-dim">${esc(p.distance_m)}m · ${esc(p.bearing)} · sol ${esc(p.sol)}</div>
        </button>`).join('')}</div>`
  return `<div class="h2g2-secao"><p class="h2g2-panel-title">Fotos próximas</p>${corpo}</div>`
}

function secaoCiencia(t) {
  const corpo = t === null
    ? '<div class="h2g2-empty-state">Nenhum alvo científico cadastrado próximo deste ponto.</div>'
    : `<div class="h2g2-small">
        <div><strong>${esc(t.nome)}</strong></div>
        ${t.medicao_curiosity ? `<div>${esc(t.medicao_curiosity)}</div>` : ''}
        ${t.mineral_crism ? `<div class="h2g2-dim">CRISM: ${esc(t.mineral_crism)}</div>` : ''}
        ${t.classe_terreno ? `<div class="h2g2-dim">Terreno: ${esc(t.classe_terreno)}</div>` : ''}
        ${t.confianca ? `<div class="h2g2-dim">Confiança: ${esc(t.confianca)}</div>` : ''}
      </div>`
  return `<div class="h2g2-secao"><p class="h2g2-panel-title">Ficha científica</p>${corpo}</div>`
}

let pedido = 0

/** Mostra o briefing de `ponto` em `el`. nomenclatura: lista de /api/nomenclature. */
export async function abrirPonto(el, ponto, nomenclatura, onFechar) {
  const meu = ++pedido
  const perto = nomeMaisProximo(nomenclatura, ponto.lat, ponto.lon)
  const topo = `
    <div class="h2g2-linha-topo">
      <p class="h2g2-panel-title">Briefing de segurança</p>
      <button class="h2g2-close-btn" data-fechar aria-label="Fechar">×</button>
    </div>
    <div class="h2g2-mono h2g2-coord">${coord(ponto)}</div>
    <div class="h2g2-dim h2g2-micro h2g2-bloco">${perto
      ? `perto de <a href="${esc(perto.feature.fonte_url)}" target="_blank" rel="noreferrer" style="color:var(--ink-2)" title="Nome oficial IAU/USGS · ${esc(perto.feature.tipo)}">${esc(perto.feature.nome)}</a> (${(perto.distance_m / 1000).toFixed(1)}km)`
      : ''}</div>`

  let fotos = null
  el.hidden = false
  el.onclick = (e) => {
    if (e.target.closest('[data-fechar]')) return onFechar()
    const f = e.target.closest('[data-foto]')
    if (f && fotos) abrirLightbox(fotos, Number(f.dataset.foto))
  }
  el.innerHTML = `${topo}<div class="h2g2-dim h2g2-mono h2g2-small">consultando /api/point...</div>`

  let data
  try {
    data = await getPoint(ponto.lat, ponto.lon)
  } catch (e) {
    if (meu === pedido) el.innerHTML = `${topo}<div class="h2g2-erro">${esc(e.message)}</div>`
    return
  }
  if (meu !== pedido) return // clique mais novo já substituiu este

  fotos = data.nearby_photos.map((p) => ({ url: p.url, sol: p.sol, camera: p.camera, caption: `${p.distance_m}m · ${p.bearing}` }))
  const alertas = data.alertas.length === 0 ? '' : `<div class="h2g2-bloco">${data.alertas
    .map((a) => `<div class="h2g2-mono h2g2-alerta" title="fonte: ${esc(a.fonte)}" style="color:${ALERTA_COR[a.nivel]}">● ${esc(a.mensagem)}</div>`)
    .join('')}</div>`

  el.innerHTML = topo + alertas + secaoElevacao(data.raster_values) + secaoFotos(data.nearby_photos) + secaoCiencia(data.science_target)
}

export function fecharPonto(el) {
  pedido++ // descarta resposta pendente
  el.hidden = true
  el.innerHTML = ''
}
