// F11: visor por voz. Lê o catálogo web/comandos.json (o mesmo que a API usa), põe o id
// (m-A…) discreto no topo de cada bloco e executa {alvo, acao, args} pelos handlers que
// app.js registra. Nada fora do catálogo executa. Plano: docs/feature-11-visor-por-voz.md
let modais = {}
const handlers = {}
let foco = null // último bloco acionado: desempata "próxima" sem bloco citado

export async function iniciarComandos() {
  const cat = await fetch('comandos.json').then((r) => r.json())
  modais = Object.fromEntries(cat.modais.map((m) => [m.id, m]))
  for (const m of cat.modais) {
    const el = m.seletor && document.querySelector(m.seletor)
    if (!el) continue // "sis": ações globais, sem bloco na tela
    el.dataset.modal = m.id
    el.dataset.modalTitulo = `${m.id} · ${m.falado[0]} · ${m.nome}`
    // .frame já usa ::before/::after nos cantos: o selo entra como elemento
    if (el.classList.contains('frame')) el.insertAdjacentHTML('afterbegin', `<span class="modal-id mono" aria-hidden="true">${m.id}</span>`)
  }
}

/** acoes: {nome: (args) => void | false | string}. false = não deu; string = o que aconteceu. */
export function registrar(id, acoes) {
  handlers[id] = { ...handlers[id], ...acoes }
}

const visivel = (el) => el && !el.hidden && el.getClientRects().length > 0

export function abertos() {
  return Object.values(modais).filter((m) => m.seletor && visivel(document.querySelector(m.seletor))).map((m) => m.id)
}

export const contexto = () => ({ abertos: abertos(), foco })

/** Ajuda falada: blocos abertos e as ações de cada um. */
export function descreverAbertos() {
  const ids = abertos()
  if (!ids.length) return 'Nenhum bloco aberto. Diga, por exemplo: Atlas, expandir.'
  return 'Blocos abertos: ' + ids.map((i) => `${modais[i].falado[0]}, ${modais[i].nome}: ${Object.keys(modais[i].acoes).join(', ').replaceAll('_', ' ')}`).join('. ') + '.'
}

/** → {ok, texto}. Valida contra o catálogo antes de chamar o handler. */
export async function executar(cmd) {
  const m = modais[cmd?.alvo]
  const a = m?.acoes[cmd.acao]
  const fn = handlers[cmd?.alvo]?.[cmd?.acao]
  if (!m || !a || !fn) return { ok: false, texto: `Comando fora do catálogo: ${cmd?.alvo} ${cmd?.acao}` }
  let r
  try {
    r = await fn(cmd.args ?? {})
  } catch (e) {
    r = `${m.nome}: falhou (${e.message})`
  }
  foco = m.id
  const ok = r === undefined || r === true
  if (ok) piscar(m)
  return { ok, texto: ok ? `${m.id} · ${m.nome}: ${a.desc}` : (typeof r === 'string' ? r : `${m.nome}: nada para ${cmd.acao} agora`) }
}

function piscar(m) {
  const el = m.seletor && document.querySelector(m.seletor)
  if (!el) return
  el.classList.remove('modal-acionado')
  void el.offsetWidth
  el.classList.add('modal-acionado')
}
