// F08: assistant history. Questions are asked only by voice (voice.js); this panel opens by itself
// with the question and shows the answer. Answers about the destination or, with no destination,
// about the current position. Local model: the wait is visible (counter).
import { ask } from '../api.js'
import { coord, esc } from './util.js'

const MAX_HISTORY = 4

/** Speech output: only local system voices, never network ones (offline). */
export function speak(text) {
  const voice = speechSynthesis.getVoices().find((v) => v.lang.startsWith('en') && v.localService)
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'en-US'
  if (voice) u.voice = voice
  speechSynthesis.cancel() // do not stack answers
  speechSynthesis.speak(u)
}

/**
 * el: <section id="assistant">.
 * currentPoint(): {lat, lon, label} of the destination or current position, or null (the API uses the base).
 * currentRoute(): open route (routeForAgent) or null; with it the API runs the route forecast.
 * openRoute({lat, lon}): the agent planned a route (plan_route tool): opens it on the map, without choosing for you.
 * showOptions(result, origin): problem reported -> new options from /api/replan, next to the current route.
 * currentPosition(): where the astronaut is ("📍 I am here"); currentPoint may be the destination with an open route.
 */
export function initAssistant(el, currentPoint, currentRoute = () => null, openRoute = () => {}, showOptions = () => {},
  currentPosition = () => null) {
  const history = [] // {question, about, answer?, sources?, error?, seconds}
  let busy = false
  let timer = null

  const about = () => {
    if (currentRoute()) return 'the open route'
    const p = currentPoint()
    return p ? `${p.label ?? 'the point'} (${coord(p)})` : 'the base (no point chosen)'
  }

  function render() {
    const items = history.map((h, i) => `
      <article class="h2g2-asst-item">
        <div class="h2g2-asst-q">› ${esc(h.question)} <span class="h2g2-dim h2g2-micro">about ${esc(h.about)}</span></div>
        ${h.answer === undefined && !h.error
          ? `<div class="h2g2-dim h2g2-mono h2g2-small" aria-live="polite">thinking on the local model… ${h.seconds}s</div>`
          : h.error
            ? `<div class="h2g2-error">${esc(h.error)}</div><div class="h2g2-dim h2g2-micro">Alerts still apply: they do not depend on the model.</div>`
            : `<p class="h2g2-asst-r">${esc(h.answer)}</p>
               <div class="h2g2-dim h2g2-micro">sources: ${esc(h.sources.join(' · ') || 'none')} · ${h.seconds}s
               ${'speechSynthesis' in window ? ` · <button type="button" class="h2g2-link-btn" data-listen="${i}">▶ listen</button>` : ''}</div>`}
      </article>`).join('')
    el.innerHTML = `<div class="h2g2-asst-hist">${items || '<p class="h2g2-dim h2g2-small">Say "Hey guide" and ask the question.</p>'}</div>`
  }

  /** byVoice: the question came from the microphone, so the answer is spoken too. */
  async function send(question, byVoice = false) {
    if (busy || !question.trim()) return
    busy = true
    const h = { question: question.trim(), about: about(), seconds: 0 }
    history.unshift(h)
    history.length = Math.min(history.length, MAX_HISTORY)
    render()
    const start = performance.now()
    timer = setInterval(() => {
      h.seconds = Math.round((performance.now() - start) / 1000)
      render()
    }, 1000)
    const p = currentPoint()
    try {
      const r = await ask(h.question, p?.lat, p?.lon, currentRoute(), currentPosition())
      Object.assign(h, { answer: r.answer, sources: r.sources })
      const route = r.actions?.findLast((a) => a.type === 'open_route')
      if (route) openRoute({ lat: route.lat, lon: route.lon })
      const replan = r.actions?.findLast((a) => a.type === 'replan')
      if (replan) showOptions(replan.result, replan.origin)
      if (byVoice) speak(`You asked: ${h.question} ${r.answer}`) // repeats what it heard: a transcription error becomes audible
    } catch (err) {
      h.error = err.message
      if (byVoice) speak('The assistant is offline. The alerts still apply.')
    } finally {
      clearInterval(timer)
      h.seconds = Math.round((performance.now() - start) / 1000)
      busy = false
      render()
    }
  }

  function open(isOpen = el.hidden) {
    el.hidden = !isOpen
    if (isOpen) render()
  }

  el.addEventListener('click', (e) => {
    const i = e.target.closest('[data-listen]')?.dataset.listen
    if (i !== undefined && history[i]?.answer) speak(history[i].answer)
  })
  // click outside the panel or Esc closes; the next spoken question reopens it
  document.addEventListener('pointerdown', (e) => {
    if (!el.hidden && !el.contains(e.target)) open(false)
  })
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !el.hidden) open(false)
  })
  return { open, render, send }
}
