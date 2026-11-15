// F11: voice viewer. Reads the catalog web/commands.json (the same one the API uses), puts the id
// (m-A…) discreetly on top of each block and executes {target, action, args} through the handlers
// app.js registers. Nothing outside the catalog executes. Plan: docs/feature-11-visor-por-voz.md
let blocks = {}
const handlers = {}
let focus = null // last block triggered: breaks the tie of "next" with no block cited

export async function initCommands() {
  const cat = await fetch('commands.json').then((r) => r.json())
  blocks = Object.fromEntries(cat.blocks.map((b) => [b.id, b]))
  for (const b of cat.blocks) {
    const el = b.selector && document.querySelector(b.selector)
    if (!el) continue // "sys": global actions, no block on screen
    el.dataset.modal = b.id
    el.dataset.modalLabel = b.spoken[0]
    el.dataset.modalTitle = `${b.id} · ${b.spoken[0]} · ${b.name}`
    // .frame already uses ::before/::after on the corners: the badge goes in as an element
    if (el.classList.contains('frame')) el.insertAdjacentHTML('afterbegin', `<span class="modal-id mono" aria-hidden="true">${b.spoken[0]}</span>`)
  }
}

/** actions: {name: (args) => void | false | string}. false = could not; string = what happened. */
export function register(id, actions) {
  handlers[id] = { ...handlers[id], ...actions }
}

const visible = (el) => el && !el.hidden && el.getClientRects().length > 0

export function openBlocks() {
  return Object.values(blocks).filter((b) => b.selector && visible(document.querySelector(b.selector))).map((b) => b.id)
}

export const context = () => ({ openBlocks: openBlocks(), focus })

/** Spoken help: open blocks and the actions of each. */
export function describeOpen() {
  const ids = openBlocks()
  if (!ids.length) return 'No block open. Say, for example: Atlas, expand.'
  return 'Open blocks: ' + ids.map((i) => `${blocks[i].spoken[0]}, ${blocks[i].name}: ${Object.keys(blocks[i].actions).join(', ').replaceAll('_', ' ')}`).join('. ') + '.'
}

/** → {ok, text}. Validates against the catalog before calling the handler. */
export async function execute(cmd) {
  const b = blocks[cmd?.target]
  const a = b?.actions[cmd.action]
  const fn = handlers[cmd?.target]?.[cmd?.action]
  if (!b || !a || !fn) return { ok: false, text: `Command outside the catalog: ${cmd?.target} ${cmd?.action}` }
  let r
  try {
    r = await fn(cmd.args ?? {})
  } catch (e) {
    r = `${b.name}: failed (${e.message})`
  }
  focus = b.id
  if (r && typeof r === 'object') { // {ok, text}: a successful result that carries text to show (no speech)
    if (r.ok) flash(b)
    return { ok: r.ok, text: r.text }
  }
  const ok = r === undefined || r === true
  if (ok) flash(b)
  return { ok, text: ok ? `${b.spoken[0]} · ${b.name}: ${a.desc}` : (typeof r === 'string' ? r : `${b.name}: nothing to ${cmd.action} right now`) }
}

function flash(b) {
  const el = b.selector && document.querySelector(b.selector)
  if (!el) return
  el.classList.remove('modal-triggered')
  void el.offsetWidth
  el.classList.add('modal-triggered')
}
