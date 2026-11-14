// F08: assistente sempre à mão (botão no topo ou tecla "/"). Responde sobre o ponto
// clicado ou, sem ponto, sobre a base. Modelo local: a espera é visível (contador).
import { perguntar } from '../api.js'
import { coord, esc } from './util.js'

const SUGESTOES = [
  'Posso subir aqui com segurança?',
  'Qual a melhor hora para a EVA hoje?',
  'Qual a previsão de temperatura para hoje?',
  'Quanta radiação vou receber hoje?',
  'Tem alvo científico perto daqui?',
]
const MAX_HISTORICO = 4

/** Voz de saída: só vozes locais do sistema, nunca as de rede (offline). */
function falar(texto) {
  const voz = speechSynthesis.getVoices().find((v) => v.lang.startsWith('pt') && v.localService)
  const u = new SpeechSynthesisUtterance(texto)
  u.lang = 'pt-BR'
  if (voz) u.voice = voz
  speechSynthesis.cancel() // não empilhar respostas
  speechSynthesis.speak(u)
}

/**
 * el: <section id="assistente">; botao: abre/fecha.
 * pontoAtual(): {lat, lon} do ponto clicado, ou null (a API usa a base).
 */
export function iniciarAssistente(el, botao, pontoAtual) {
  const historico = [] // {pergunta, sobre, resposta?, fontes?, erro?, segundos}
  let ocupado = false
  let relogio = null

  const sobre = () => {
    const p = pontoAtual()
    return p ? `o ponto clicado (${coord(p)})` : 'a base (nenhum ponto escolhido)'
  }

  function render() {
    const campo = el.querySelector('input[name=q]')
    const digitado = campo?.value ?? ''
    const comFoco = document.activeElement === campo
    const itens = historico.map((h, i) => `
      <article class="h2g2-ass-item">
        <div class="h2g2-ass-q">› ${esc(h.pergunta)} <span class="h2g2-dim h2g2-micro">sobre ${esc(h.sobre)}</span></div>
        ${h.resposta === undefined && !h.erro
          ? `<div class="h2g2-dim h2g2-mono h2g2-small" aria-live="polite">pensando no modelo local… ${h.segundos}s</div>`
          : h.erro
            ? `<div class="h2g2-erro">${esc(h.erro)}</div><div class="h2g2-dim h2g2-micro">Os alertas continuam valendo: não dependem do modelo.</div>`
            : `<p class="h2g2-ass-r">${esc(h.resposta)}</p>
               <div class="h2g2-dim h2g2-micro">fontes: ${esc(h.fontes.join(' · ') || 'nenhuma')} · ${h.segundos}s
               ${'speechSynthesis' in window ? ` · <button type="button" class="h2g2-link-btn" data-ouvir="${i}">▶ ouvir</button>` : ''}</div>`}
      </article>`).join('')
    el.innerHTML = `
      <div class="h2g2-linha-topo">
        <p class="h2g2-panel-title">Pergunte ao H2G2 · assistente local</p>
        <button class="h2g2-close-btn" data-fechar aria-label="Fechar assistente">×</button>
      </div>
      <form class="h2g2-ass-form">
        <input name="q" maxlength="500" required autocomplete="off" placeholder="Pergunte sobre ${esc(sobre())}" aria-label="Pergunta ao assistente">
        <button class="h2g2-mono" ${ocupado ? 'disabled' : ''}>perguntar</button>
      </form>
      <div class="h2g2-ass-sugestoes">${SUGESTOES.map((s) => `<button type="button" data-sugestao="${esc(s)}" ${ocupado ? 'disabled' : ''}>${esc(s)}</button>`).join('')}</div>
      <div class="h2g2-dim h2g2-micro">Responde só com o pacote de dados local: cita a fonte, diz "não sei" quando não tem o dado e nunca decide pela tripulação.</div>
      ${itens ? `<div class="h2g2-ass-hist">${itens}</div>` : ''}`
    const novo = el.querySelector('input[name=q]')
    novo.value = digitado
    if (comFoco) novo.focus()
  }

  async function enviar(pergunta) {
    if (ocupado || !pergunta.trim()) return
    ocupado = true
    const h = { pergunta: pergunta.trim(), sobre: sobre(), segundos: 0 }
    historico.unshift(h)
    historico.length = Math.min(historico.length, MAX_HISTORICO)
    render()
    const inicio = performance.now()
    relogio = setInterval(() => {
      h.segundos = Math.round((performance.now() - inicio) / 1000)
      render()
    }, 1000)
    const p = pontoAtual()
    try {
      const r = await perguntar(h.pergunta, p?.lat, p?.lon)
      Object.assign(h, { resposta: r.resposta, fontes: r.fontes })
    } catch (err) {
      h.erro = err.message
    } finally {
      clearInterval(relogio)
      h.segundos = Math.round((performance.now() - inicio) / 1000)
      ocupado = false
      render()
      el.querySelector('input[name=q]')?.focus()
    }
  }

  function abrir(aberto = el.hidden) {
    el.hidden = !aberto
    botao.classList.toggle('on', aberto)
    botao.setAttribute('aria-expanded', String(aberto))
    if (aberto) {
      render()
      el.querySelector('input[name=q]').focus()
    }
  }

  botao.addEventListener('click', () => abrir())
  el.addEventListener('submit', (e) => {
    e.preventDefault()
    const q = e.target.q.value
    e.target.q.value = ''
    enviar(q)
  })
  el.addEventListener('click', (e) => {
    if (e.target.closest('[data-fechar]')) return abrir(false)
    const s = e.target.closest('[data-sugestao]')?.dataset.sugestao
    if (s) return enviar(s)
    const i = e.target.closest('[data-ouvir]')?.dataset.ouvir
    if (i !== undefined && historico[i]?.resposta) falar(historico[i].resposta)
  })
  // "/" abre de qualquer lugar (fora de campo de texto); Esc fecha
  document.addEventListener('keydown', (e) => {
    const digitando = e.target.closest?.('input, textarea')
    if (e.key === '/' && !digitando && el.hidden) {
      e.preventDefault()
      abrir(true)
    } else if (e.key === 'Escape' && !el.hidden) abrir(false)
  })
  return { abrir, render }
}
