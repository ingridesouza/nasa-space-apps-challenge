// Seletor de camadas compacto (só no mapa expandido). Eventos em app.js via
// data-toggle / data-opacidade / data-minimizar.
import { PLANNED_LAYERS, TOGGLEABLE_LAYERS } from '../layers.js'
import { esc } from './util.js'

function linha(id, on, rotulo, titulo = '', opacidade = null) {
  return `<div class="cam-linha">
      <button type="button" role="switch" aria-checked="${on}" aria-label="${esc(rotulo)}" data-toggle="${id}" class="sw ${on ? 'on' : ''}"><span></span></button>
      <span class="cam-nome" title="${esc(titulo)}">${esc(rotulo)}</span>
      ${on && opacidade !== null ? `<input type="range" class="cam-op" min="0" max="1" step="0.05" value="${opacidade}" data-opacidade="${id}" aria-label="Opacidade ${esc(rotulo)}">` : ''}
    </div>`
}

/** estado: { camadas: {id: {visible, opacity}}, fotosVisiveis, nFotos, trilhaVisivel } */
export function renderCamadas(el, estado) {
  const planejadas = PLANNED_LAYERS.map((l) => `<span title="${esc(l.motivo)}">${esc(l.label)} (${l.status === 'fora_de_escopo' ? 'fora de escopo' : 'em breve'})</span>`).join(' · ')
  el.innerHTML = `
    <div class="cam-topo"><span class="eyebrow">Camadas</span>
      <button type="button" class="ibtn ibtn-sm" data-minimizar title="Minimizar mapa (Esc)">✕</button></div>
    ${TOGGLEABLE_LAYERS.map((l) => linha(l.id, estado.camadas[l.id].visible, l.label, '', estado.camadas[l.id].opacity)).join('')}
    ${linha('fotos', estado.fotosVisiveis, `Rastro do rover (${estado.nFotos})`, 'Posições reais das fotos Navcam')}
    ${linha('trilha', estado.trilhaVisivel, 'Trilha do Curiosity', 'Paradas reais, coloridas pela inclinação medida pelo rover: verde seguro, âmbar atenção, vermelho perigo.')}
    <p class="rotulo mono">${planejadas}</p>`
}
