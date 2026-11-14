// Briefing de segurança do ponto clicado (antes PointInfoPanel + NearbyPhotosSection
// + ScienceTargetSection).
import { getFichaCientifica, getPanorama, getPoint } from '../api.js'
import { abrirLightbox } from './lightbox.js'
import { alertasHtml, coord, esc, nomeMaisProximo, veredito } from './util.js'

const CATEGORIA_LABEL = { topografica: 'Topografia', optica: 'Óptica', termica: 'Térmica', espectral_quimica: 'Mineralogia' }

/** Camada que virou o elevacao_m "oficial" (PRIORIDADE_ELEVACAO em api/raster_sampling.py). */
function camadaPrincipal(fontes) {
  if ('dtm_hirise_1m' in fontes) return 'dtm_hirise_1m'
  if ('mola_topografia_regional' in fontes) return 'mola_topografia_regional'
  return Object.keys(fontes)[0] ?? null
}

const GRAVIDADE = ['seguro', 'atencao', 'perigo']

/** Selo nunca contradiz alerta: vale o pior entre o mapa e o que o rover mediu por perto. */
function seloDoPonto(statusMapa, alertas) {
  let status = statusMapa
  for (const a of alertas) {
    if (['terreno_historico', 'inclinacao', 'risco_previsto'].includes(a.tipo) && GRAVIDADE.indexOf(a.nivel) > GRAVIDADE.indexOf(status)) status = a.nivel
  }
  const semHistorico = alertas.some((a) => a.tipo === 'sem_historico')
  if (semHistorico && status === 'seguro') {
    return veredito('atencao', [{ ok: false, label: 'só mapa de órbita: o rover nunca passou aqui' }], 'Não verificado: só mapa de órbita')
  }
  return veredito(status)
}

function secaoElevacao(rv, alertas = [], risco = null) {
  const camada = camadaPrincipal(rv.fontes)
  const principal =
    rv.elevacao_m === null
      ? '<div class="h2g2-empty-state">Fora da área de teste com dado baixado (ver PROXIMOS-PASSOS.md).</div>'
      : `<div class="h2g2-bloco">
          ${rv.slope_status ? seloDoPonto(rv.slope_status, alertas) : ''}
          <div class="h2g2-card" style="margin-top:var(--s-2)">
            <div class="h2g2-display h2g2-elev">${rv.elevacao_m.toFixed(1)}<span class="h2g2-mono h2g2-small h2g2-dim"> m</span></div>
            ${rv.slope_deg !== null ? `<div class="h2g2-dim h2g2-mono h2g2-small">slope ${rv.slope_deg.toFixed(2)}°</div>` : ''}
            ${risco ? `<div class="h2g2-small" style="margin-top:var(--s-1)${risco.chance_pct >= 20 ? ';color:var(--verdict-atencao)' : ''}" title="${esc(risco.metodo)} · ${esc(risco.fonte)}">
              chance real ≥${esc(risco.limite_deg)}°: <strong>${esc(risco.chance_pct)}%</strong>
              <div class="h2g2-dim h2g2-micro">estimado: ${esc(risco.acima)} de ${esc(risco.n)} paradas do rover com o mapa em ${esc(risco.faixa_mapa)}</div></div>` : ''}
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
  return `<div class="h2g2-secao h2g2-extra"><p class="h2g2-panel-title">Fotos próximas</p>${corpo}</div>`
}

const fonte = (l) => (l.fonte_url
  ? `<a href="${esc(l.fonte_url)}" target="_blank" rel="noreferrer" style="color:var(--ink-3)">fonte</a>`
  : esc(l.fonte_arquivo))

/** Ficha da F04 (/science/card). Linhas mock ficam de fora (CLAUDE.md): só a contagem aparece. */
function fichaF04(f) {
  if (!f?.alvo) return ''
  const linhas = [...f.linhas, ...f.contexto].filter((l) => l.secao !== 'nome')
  const reais = linhas.filter((l) => l.confianca !== 'mock')
  const ocultas = linhas.length - reais.length
  const a = f.alvo
  return `<div class="h2g2-small h2g2-sep">
    <div><strong>${esc(a.nome)}</strong> <span class="h2g2-dim">· ${esc(a.tipo_rotulo)} · ${esc(a.distancia_rotulo)}</span></div>
    ${f.aviso_posicao ? `<div class="h2g2-dim h2g2-micro">${esc(f.aviso_posicao)}</div>` : ''}
    ${reais.map((l) => `<div style="margin-top:var(--s-1)">${esc(l.texto)}
      <span class="h2g2-dim h2g2-micro">· ${esc(l.confianca_rotulo)} · ${fonte(l)}</span></div>`).join('')}
    ${ocultas ? `<div class="h2g2-dim h2g2-micro" style="margin-top:var(--s-1)">${ocultas} medição(ões) de exemplo ocultas: fonte ainda não ligada ao pacote.</div>` : ''}
    ${f.mastcam ? `<img class="h2g2-mastcam" src="${esc(f.mastcam.img)}" alt="${esc(f.mastcam.rotulo)}" loading="lazy">
      <div class="h2g2-dim h2g2-micro">${esc(f.mastcam.rotulo)} · ${esc(f.mastcam.credito)}</div>` : ''}
  </div>`
}

function secaoPanorama(p) {
  if (!p) return ''
  const corpo = p.found
    ? `<div class="h2g2-pano" data-pano></div><div class="h2g2-dim h2g2-micro">${esc(p.rotulo)} · ${esc(p.credito)}</div>`
    : `<div class="h2g2-empty-state">${esc(p.mensagem)}.</div>`
  return `<div class="h2g2-secao h2g2-extra"><p class="h2g2-panel-title">Panorama no ponto</p>${corpo}</div>`
}

function secaoCiencia(t, f04) {
  const corpo = t === null
    ? (f04?.alvo ? '' : '<div class="h2g2-empty-state">Nenhum alvo científico cadastrado próximo deste ponto.</div>')
    : `<div class="h2g2-small">
        <div><strong>${esc(t.nome)}</strong></div>
        ${t.medicao_curiosity ? `<div>${esc(t.medicao_curiosity)}</div>` : ''}
        ${t.mineral_crism ? `<div class="h2g2-dim">CRISM: ${esc(t.mineral_crism)}</div>` : ''}
        ${t.classe_terreno ? `<div class="h2g2-dim">Terreno: ${esc(t.classe_terreno)}</div>` : ''}
        ${t.confianca ? `<div class="h2g2-dim">Confiança: ${esc(t.confianca)}</div>` : ''}
      </div>`
  return `<div class="h2g2-secao h2g2-extra"><p class="h2g2-panel-title">Ficha científica</p>${corpo}${fichaF04(f04)}</div>`
}

let pedido = 0
let viewer = null // Pannellum do panorama aberto

function destruirPanorama() {
  viewer?.destroy()
  viewer = null
}

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

  destruirPanorama()
  // F03/F04 são extras: se falharem, o briefing de segurança sai do mesmo jeito
  const extras = Promise.allSettled([getPanorama(ponto.lat, ponto.lon), getFichaCientifica(ponto.lat, ponto.lon)])
  let data
  try {
    data = await getPoint(ponto.lat, ponto.lon)
  } catch (e) {
    if (meu === pedido) el.innerHTML = `${topo}<div class="h2g2-erro">${esc(e.message)}</div>`
    return
  }
  const [pano, f04] = (await extras).map((r) => (r.status === 'fulfilled' ? r.value : null))
  if (meu !== pedido) return // clique mais novo já substituiu este

  fotos = data.nearby_photos.map((p) => ({ url: p.url, sol: p.sol, camera: p.camera, caption: `${p.distance_m}m · ${p.bearing}` }))
  const alertas = data.alertas.length === 0 ? '' : `<div class="h2g2-bloco">${alertasHtml(data.alertas)}</div>`

  // fotos por último: podem ser 100+ e empurrariam ficha e pergunta pra fora da tela
  el.innerHTML = topo + alertas + secaoElevacao(data.raster_values, data.alertas, data.previsao_inclinacao) + secaoCiencia(data.science_target, f04) +
    secaoPanorama(pano) + secaoFotos(data.nearby_photos)
  const div = el.querySelector('[data-pano]')
  if (div && window.pannellum) {
    viewer = window.pannellum.viewer(div, {
      ...pano.pannellum,
      hotSpots: [{ pitch: 0, yaw: pano.pannellum.yaw, type: 'info', text: 'direção do ponto clicado' }],
    })
  }
}

export function fecharPonto(el) {
  pedido++ // descarta resposta pendente
  destruirPanorama()
  el.hidden = true
  el.innerHTML = ''
}
