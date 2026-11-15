// F08: assistant always at hand (pill at the top or the "/" key). Answers about the destination
// or, with no destination, about the current position. Local model: the wait is visible (counter).
import { ask } from '../api.js'
import { coord, esc } from './util.js'

const MAX_HISTORY = 4

/** Speech output: only local system voices, never network ones (offline). */
function speak(text) {
  const voice = speechSynthesis.getVoices().find((v) => v.lang.startsWith('en') && v.localService)
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'en-US'
  if (voice) u.voice = voice
  speechSynthesis.cancel() // do not stack answers
  speechSynthesis.speak(u)
}

/**
 * el: <section id="assistant">; button: opens/closes.
 * currentPoint(): {lat, lon, label} of the destination or current position, or null (the API uses the base).
 */
export function initAssistant(el, button, currentPoint) {
  const history = [] // {question, about, answer?, sources?, error?, seconds}
  let busy = false
  let timer = null

  const about = () => {
    const p = currentPoint()
    return p ? `${p.label ?? 'the point'} (${coord(p)})` : 'the base (no point chosen)'
  }

  function render() {
    const field = el.querySelector('input[name=q]')
    const typed = field?.value ?? ''
    const focused = document.activeElement === field
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
    el.innerHTML = `
      <form class="h2g2-asst-form">
        <input name="q" maxlength="500" required autocomplete="off" aria-label="Question for the assistant">
        <button class="h2g2-mono" ${busy ? 'disabled' : ''}>ask</button>
      </form>
      ${items ? `<div class="h2g2-asst-hist">${items}</div>` : ''}`
    const fresh = el.querySelector('input[name=q]')
    fresh.value = typed
    if (focused) fresh.focus()
  }

  async function send(question) {
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
      const r = await ask(h.question, p?.lat, p?.lon)
      Object.assign(h, { answer: r.answer, sources: r.sources })
    } catch (err) {
      h.error = err.message
    } finally {
      clearInterval(timer)
      h.seconds = Math.round((performance.now() - start) / 1000)
      busy = false
      render()
      el.querySelector('input[name=q]')?.focus()
    }
  }

  function open(isOpen = el.hidden) {
    el.hidden = !isOpen
    button.classList.toggle('on', isOpen)
    button.setAttribute('aria-expanded', String(isOpen))
    if (isOpen) {
      render()
      el.querySelector('input[name=q]').focus()
    }
  }

  button.addEventListener('click', () => open())
  el.addEventListener('submit', (e) => {
    e.preventDefault()
    const q = e.target.q.value
    e.target.q.value = ''
    send(q)
  })
  el.addEventListener('click', (e) => {
    const i = e.target.closest('[data-listen]')?.dataset.listen
    if (i !== undefined && history[i]?.answer) speak(history[i].answer)
  })
  // click outside the panel (and outside the pill) closes; "/" opens from anywhere (outside a text field); Esc closes
  document.addEventListener('pointerdown', (e) => {
    if (!el.hidden && !el.contains(e.target) && !button.contains(e.target)) open(false)
  })
  document.addEventListener('keydown', (e) => {
    const typing = e.target.closest?.('input, textarea')
    if (e.key === '/' && !typing && el.hidden) {
      e.preventDefault()
      open(true)
    } else if (e.key === 'Escape' && !el.hidden) open(false)
  })
  return { open, render }
}
