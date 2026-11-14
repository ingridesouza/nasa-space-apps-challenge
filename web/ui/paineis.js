// HUD, painel de camadas e painel de condições (antes TopHud, LayerControlPanel, ConditionsPanel).
import { mosaicUrl } from '../api.js'
import { LAYER_MAXZOOM, PLANNED_LAYERS, TOGGLEABLE_LAYERS } from '../layers.js'
import { coord, esc, num } from './util.js'

/** Zoom real mais detalhado baixado (HiRISE) -- além disso é só upscale. */
const ZOOM_REAL_MAXIMO = Math.max(...Object.values(LAYER_MAXZOOM))

export function renderHud(el, { ponto, sol, zoom }) {
  const alem = zoom !== null && zoom > ZOOM_REAL_MAXIMO
  el.innerHTML = `
    <div>
      <div class="h2g2-display h2g2-hud-titulo">H2G2 <span style="color:var(--mars2)">·</span> Mapa hiperlocal do boxwork</div>
      <div class="h2g2-dim h2g2-mono h2g2-hud-sub">CRATERA GALE · MONTE SHARP</div>
    </div>
    <div class="h2g2-mono h2g2-hud-dir">
      <div>
        <span class="h2g2-dim">sol </span><span>${esc(sol ?? '—')}</span>
        ${zoom === null ? '' : `<span class="h2g2-dim"> · zoom </span>
          <span style="color:${alem ? 'var(--amber)' : 'var(--ink)'}">${zoom.toFixed(1)}</span>
          ${alem ? `<span class="h2g2-dim h2g2-micro"> (além do real, z${ZOOM_REAL_MAXIMO})</span>` : ''}`}
      </div>
      <div>${ponto ? `<span style="color:var(--hud-cyan)">${coord(ponto)}</span>` : '<span class="h2g2-dim">clique no mapa</span>'}</div>
    </div>`
}

function linhaSwitch(id, on, miniatura, rotulo, titulo = '') {
  return `<div class="h2g2-linha">
      <div class="h2g2-linha" style="justify-content:flex-start;min-width:0">
        ${miniatura}<span class="h2g2-small" title="${esc(titulo)}">${esc(rotulo)}</span>
      </div>
      <button type="button" role="switch" aria-checked="${on}" aria-label="${esc(rotulo)}" data-toggle="${id}" class="h2g2-switch ${on ? 'on' : ''}"><span></span></button>
    </div>`
}

/** Painel de camadas. estado: { camadas: {id: {visible, opacity}}, fotosVisiveis, nFotos, trilhaVisivel }.
 * Eventos são tratados em app.js via data-toggle / data-opacidade. */
export function renderCamadas(el, estado) {
  const linhaCamada = (l) => {
    const s = estado.camadas[l.id]
    return `<div class="h2g2-layer-row ${s.visible ? 'on' : ''}">
        ${linhaSwitch(l.id, s.visible, `<img class="h2g2-thumb" src="${mosaicUrl(l.id)}" alt="" loading="lazy">`, l.label)}
        <input type="range" min="0" max="1" step="0.05" value="${s.opacity}" ${s.visible ? '' : 'disabled'} data-opacidade="${l.id}" aria-label="Opacidade ${esc(l.label)}">
      </div>`
  }
  el.innerHTML = `
    <p class="h2g2-panel-title">Camadas</p>
    ${TOGGLEABLE_LAYERS.filter((l) => l.grupo === 'base').map(linhaCamada).join('')}
    <div class="h2g2-sep">
      ${TOGGLEABLE_LAYERS.filter((l) => l.grupo === 'overlay').map(linhaCamada).join('')}
      <div class="h2g2-layer-row ${estado.fotosVisiveis ? 'on' : ''}">
        ${linhaSwitch('fotos', estado.fotosVisiveis, '<div class="h2g2-thumb" style="color:#f2b33d">📷</div>', `Rastro do rover (${estado.nFotos})`)}
      </div>
      <div class="h2g2-layer-row ${estado.trilhaVisivel ? 'on' : ''}">
        ${linhaSwitch(
          'trilha',
          estado.trilhaVisivel,
          '<div class="h2g2-thumb" style="color:var(--hud-cyan)">〰️</div>',
          'Trilha do Curiosity (inclinação medida)',
          'Paradas reais do Curiosity, coloridas pela inclinação que o rover mediu no chão (não a do DTM) -- verde seguro, âmbar atenção, vermelho perigo (feature 08).',
        )}
      </div>
    </div>
    <div class="h2g2-sep" style="padding-top:var(--s-3)">
      ${PLANNED_LAYERS.map((l) => `<div class="h2g2-dim h2g2-planejada" title="${esc(l.motivo)}">
          <span>${esc(l.label)}</span><span class="h2g2-mono h2g2-micro">${l.status === 'fora_de_escopo' ? 'fora de escopo' : 'em breve'}</span>
        </div>`).join('')}
    </div>`
}

/** Clima (REMS) + radiação (RAD) do sol de referência -- dado real cacheado, não ao vivo. */
export function renderCondicoes(el, { conditions: c, error }) {
  const corpo = error
    ? '<div class="h2g2-dim h2g2-mono h2g2-small">indisponível</div>'
    : !c
      ? '<div class="h2g2-dim h2g2-mono h2g2-small">carregando...</div>'
      : `<div class="h2g2-card h2g2-stat-grid">
          <div><span class="h2g2-stat-label">Temp</span><span class="h2g2-stat-value h2g2-small">${num(c.rems.temp_min_c, 1)}° a ${num(c.rems.temp_max_c, 1)}°C</span></div>
          <div><span class="h2g2-stat-label">Pressão</span><span class="h2g2-stat-value h2g2-small">${num(c.rems.pressao_pa, 0)} Pa</span></div>
          <div><span class="h2g2-stat-label">UV pico</span><span class="h2g2-stat-value h2g2-small">${num(c.rems.uv_pico, 2)} W/m²</span></div>
          <div><span class="h2g2-stat-label">Umidade</span><span class="h2g2-stat-value h2g2-small">${num(c.rems.umidade_pct, 1)}%</span></div>
          <div class="h2g2-full h2g2-sep"><span class="h2g2-stat-label">Dose RAD</span><span class="h2g2-stat-value" style="color:var(--ember)">${num(c.rad.dose_estimada_ugy_por_dia, 1)} µGy/dia</span></div>
        </div>`
  el.innerHTML = `<p class="h2g2-panel-title">Condições · sol ${esc(c?.sol ?? '—')}</p>${corpo}`
}
