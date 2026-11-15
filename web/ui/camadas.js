// Seletor de camadas compacto (só no mapa expandido). CTX e HiRISE (grupo 'base')
// ficam sempre ligadas a 100% e não aparecem aqui. Eventos em app.js via
// data-toggle / data-opacidade.
import { PLANNED_LAYERS, TI_LEGENDA, TOGGLEABLE_LAYERS } from '../layers.js'
import { esc } from './util.js'

function linha(id, on, rotulo, titulo = '', opacidade = null) {
  return `<div class="cam-linha">
      <button type="button" role="switch" aria-checked="${on}" aria-label="${esc(rotulo)}" data-toggle="${id}" class="sw ${on ? 'on' : ''}"><span></span></button>
      <span class="cam-nome" title="${esc(titulo)}">${esc(rotulo)}</span>
      ${on && opacidade !== null ? `<input type="range" class="cam-op" min="0" max="1" step="0.05" value="${opacidade}" data-opacidade="${id}" aria-label="Opacidade ${esc(rotulo)}">` : ''}
    </div>`
}

function legendaTI() {
  return `<div class="cam-legenda" title="Inércia térmica (J m⁻² K⁻¹ s⁻½), THEMIS/USGS, 100 m por célula">
      <span class="cam-grad" style="background:${TI_LEGENDA.gradiente}"></span>
      <span class="mono">${TI_LEGENDA.min} solto</span><span class="mono">firme ${TI_LEGENDA.max}</span>
    </div>`
}

/** estado: { camadas: {id: {visible, opacity}} } */
export function renderCamadas(el, estado) {
  const planejadas = PLANNED_LAYERS.map((l) => `<span title="${esc(l.motivo)}">${esc(l.label)} (${l.status === 'fora_de_escopo' ? 'fora de escopo' : 'em breve'})</span>`).join(' · ')
  el.innerHTML = `
    ${TOGGLEABLE_LAYERS.filter((l) => l.grupo !== 'base').map((l) => linha(l.id, estado.camadas[l.id].visible, l.label, '', estado.camadas[l.id].opacity)).join('')}
    ${estado.camadas.themis_ti?.visible ? legendaTI() : ''}
    <p class="rotulo mono">${planejadas}</p>`
}
