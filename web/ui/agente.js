// F08 fase 2: caixa de pergunta ao agente local (POST /api/ask), dentro do briefing do ponto.
import { perguntar } from '../api.js'
import { esc } from './util.js'

/** Voz de saída (etapa 4): só vozes locais do sistema, nunca as de rede (offline). */
function falar(texto) {
  const voz = speechSynthesis.getVoices().find((v) => v.lang.startsWith('pt') && v.localService)
  const u = new SpeechSynthesisUtterance(texto)
  u.lang = 'pt-BR'
  if (voz) u.voice = voz
  speechSynthesis.cancel() // não empilhar respostas
  speechSynthesis.speak(u)
}

export function renderAgente(el, ponto) {
  el.innerHTML = `
    <p class="h2g2-panel-title">Pergunte ao H2G2</p>
    <form class="h2g2-agente">
      <input name="q" maxlength="500" required autocomplete="off" placeholder="ex.: dá pra subir aqui?" aria-label="Pergunta sobre este ponto">
      <button class="h2g2-mono">perguntar</button>
    </form>
    <div class="h2g2-small h2g2-agente-saida" aria-live="polite"></div>`
  const form = el.querySelector('form')
  const saida = el.querySelector('.h2g2-agente-saida')
  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    const q = form.q.value.trim()
    if (!q) return
    form.querySelector('button').disabled = true
    saida.innerHTML = '<span class="h2g2-dim h2g2-mono">pensando… (modelo local, pode levar ~25 s)</span>'
    try {
      const r = await perguntar(q, ponto.lat, ponto.lon)
      saida.innerHTML = `<p>${esc(r.resposta)}</p>
        <div class="h2g2-dim h2g2-micro">fontes: ${esc(r.fontes.join(' · ') || 'nenhuma')}</div>
        ${'speechSynthesis' in window ? '<button type="button" class="h2g2-link-btn" data-ouvir>▶ ouvir resposta</button>' : ''}`
      saida.querySelector('[data-ouvir]')?.addEventListener('click', () => falar(r.resposta))
    } catch (err) {
      // alertas já estão no topo do briefing: são regras fixas e não dependem do modelo
      saida.innerHTML = `<div class="h2g2-erro">${esc(err.message)}</div>
        <div class="h2g2-dim h2g2-micro">Os alertas acima continuam valendo.</div>`
    } finally {
      form.querySelector('button').disabled = false
    }
  })
}
