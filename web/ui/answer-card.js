// F08 · Answer card: the dynamic card that replaced the science card modal.
// Shows the structured answer of /api/ask (card built by rule: verdict, facts, options,
// target, missing) or, with no question yet, the science card of the route destination.
// Nothing here computes a value: every number comes from the API with its source.
import { paginate } from './pages.js'
import { esc } from './util.js'

const VERDICT_TAG = { stop: 'tag-red', caution: 'tag-amber', no_alert: 'tag-ok', unknown: '' }
const STATUS = { ok: '✅', caution: '⚠️', danger: '⛔' }

const fact = (f) => `<li class="ans-fact">
  <div class="ans-fact-top${f.value.length > 32 ? ' long' : ''}"><span class="sci-sec">${esc(f.label)}</span><span class="ans-value">${esc(f.value)}</span></div>
  ${f.hint ? `<p class="caption mono">${esc(f.hint)}</p>` : ''}
  <p class="caption mono">${esc(f.confidence)} · ${esc(f.source)}</p></li>`

const option = (o) => `<li><button type="button" class="ans-option${o.suggested ? ' suggested' : ''}" data-route-type="${esc(o.type)}">
  <span class="ans-option-n mono">${o.n}</span>
  <span><b>${STATUS[o.status] ?? ''} ${esc(o.name)}</b>${o.suggested ? ' <span class="tag tag-ok">suggested</span>' : ''}
  <span class="caption mono">${esc(o.why)}</span></span></button></li>`

function answerHtml({ card, answer, error, seconds }) {
  let h = ''
  if (card === undefined && !error) return `<p class="empty loading"><span class="spinner"></span>thinking on the local model… ${seconds}s</p>`
  if (card?.answer ?? answer) h += `<p class="ans-line">${esc(card?.answer ?? answer)}</p>`
  // the technical error stays in the assistant panel; here only what the astronaut needs to know
  else if (error) h += `<p class="caption mono warning">⚠ ${card ? 'Local model offline: blocks from the fixed rules only.' : esc(error)}</p>`
  // a decision comes first: the options stay together on the first page
  if (card?.options?.length) h += `<ol class="ans-options">${card.options.map(option).join('')}</ol><p class="caption mono">Tap a route to open it. You decide.</p>`
  const v = card?.verdict
  if (v?.because?.length) h += `<ul class="ans-because ${esc(v.level)}">${v.because.map((b) => `<li><p class="sci-txt">${esc(b.text)}</p><p class="caption mono">${esc(b.source)}</p></li>`).join('')}</ul>`
  if (v?.note) h += `<p class="caption mono">${esc(v.note)}</p>`
  if (card?.facts?.length) h += `<ul class="ans-facts">${card.facts.map(fact).join('')}</ul>`
  if (card?.missing?.length) h += `<p class="caption mono ans-missing">No data: ${card.missing.map(esc).join(' · ')}</p>`
  if (card?.target) h += '<button type="button" class="link-btn ans-more" data-science>Science details ›</button>'
  return h
}

/**
 * el: <details id="c-answer">. onRouteType(type): an option was chosen (opens that route variant).
 * Returns { showPlace(science, open), showAnswer(item, open), paginate }.
 */
export function initAnswerCard(el, { onRouteType = () => {}, onRender = () => {} } = {}) {
  const name = el.querySelector('.answer-name')
  const tag = el.querySelector('.answer-tag')
  const body = el.querySelector('.answer-body')
  const repaginate = () => paginate(body, { sel: ':scope > :not(ul), :scope > ul > li', max: () => innerHeight * 0.42 })
  let current = null // answer item on screen: "Science details" opens its full science card

  function paint(title, tagText, tagClass, html, open) {
    const wasOpen = el.open
    el.hidden = false
    el.open = open || wasOpen
    name.textContent = title
    tag.textContent = tagText
    tag.className = `answer-tag tag ${tagClass}`
    tag.hidden = !tagText
    body.innerHTML = html
    requestAnimationFrame(() => { repaginate(); onRender() })
  }

  /** science: /science/card output, 'loading' or 'error' (destination of the route, no question yet). */
  function showPlace(science, open = false) {
    const [title, kind] = H2G2Card.title(science)
    paint(title, kind, 'tag-red', H2G2Card.html(science), open && science !== 'loading')
  }

  /** item: {question, card?, answer?, error?, seconds}. Opens the card: the answer is what the astronaut asked for. */
  function showAnswer(item) {
    const v = item.card?.verdict
    const title = `› ${item.question}`
    current = item
    paint(title, v?.label ?? item.card?.title ?? '', VERDICT_TAG[v?.level] ?? '', answerHtml(item), true)
  }

  el.addEventListener('toggle', () => { if (el.open) repaginate() })
  el.addEventListener('click', (e) => {
    const t = e.target.closest('[data-route-type]')?.dataset.routeType
    if (t) onRouteType(t)
    if (e.target.closest('[data-science]') && current?.card?.target) showPlace(current.card.target, true)
  })
  return { showPlace, showAnswer, paginate: repaginate }
}
